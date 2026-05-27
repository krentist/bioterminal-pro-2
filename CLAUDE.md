# BioTerminal Pro — CLAUDE.md

## What this project is

BioTerminal Pro is a Bloomberg-terminal-style biotech investment research platform targeting
Hong Kong and US markets. It is a **React SPA** (pre-compiled Vite/Perplexity frontend)
served by a **FastAPI Python backend**. Users type a ticker (e.g. `MRNA`, `6160.HK`) and get
a full-screen investment research terminal: live price, OHLCV chart, fundamentals, clinical
trial pipeline, ML confidence signal, DCF valuation, Monte Carlo scenarios, alpha screener,
bear-case risk analysis, and backtested strategy performance.

**Primary interface:** `server.py` (FastAPI). NOT `app.py` (Streamlit is an unused fallback).

**How to run:**
```
uvicorn server:app --reload --port 8000
# then open http://localhost:8000
```

---

## Strategic Goal: HKICTA 2026 FinTech Award

**Target stream:** Emerging FinTech (Non-Web3)
**Submission timeline:** 3+ months available from May 2026
**Eligibility:** Owner is a HK resident (individual)
**Critical path:** Rule 4 requires the product to have been publicly available for ≥3 months
before the submission deadline — **deployment must happen first, everything else second.**

### How judging criteria map to the codebase

| Criterion | Weight | Primary code files | Current gap |
|---|---|---|---|
| Innovation & Creativity | 30% | `model.py`, `pipeline_analyzer.py`, `rnpv_calculator.py`, news sentiment in `server.py` | Sentiment is keyword regex; no LLM; HK adapter stubs |
| Functionality | 25% | `exchanges/hk.py`, all API routes in `server.py` | HK `get_trials`, `get_flow_data`, `get_filings` all return empty DataFrames |
| Market Potential | 25% | Deployment, `alpha_screener.py`, usage analytics | Not deployed; no GBA/dual-listing features; no user evidence |
| Benefits & Impact | 10% | All modules | No quantified outcomes; HK impact is theoretical |
| Quality | 10% | All modules | No auth; CORS is open; no tests; no rate limiting |

### "Best Use of AI" bonus category
Each of the eight HKICTA categories also awards a separate "Best Use of AI" prize.
BioTerminal qualifies if LLM-based analysis is integrated, documented, and governed
(explainability + data privacy noted). Target: Claude API for news sentiment and pipeline
risk summarization, with prompt caching.

---

## Architecture

```
index.html + assets/          ← Pre-compiled React SPA (do NOT modify)
server.py                     ← FastAPI: 15 API routes + serves the SPA
data_fetcher.py               ← Data layer: primitives + high-level API
exchanges/
  __init__.py                 ← Factory: get_exchange_adapter(ticker)
  base.py                     ← ABC: 4 abstract + 4 default-raise methods
  us.py                       ← US adapter (yfinance + ClinicalTrials.gov)
  hk.py                       ← HK adapter (yfinance; CCASS/HKEXnews STUBS)
pipeline_analyzer.py          ← Enrich/summarise clinical trial DataFrames
rnpv_calculator.py            ← Risk-adjusted NPV (BIO/Informa phase probs)
model.py                      ← RandomForest prediction engine
backtester.py                 ← RSI+MACD signal backtest
alpha_screener.py             ← 5-dimension biotech screener
devils_advocate.py            ← Bear-case risk factor analysis
earnings_analyzer.py          ← EPS history, analyst targets
utils.py                      ← Formatting helpers + exchange map
app.py                        ← Streamlit fallback (not primary — ignore)
```

### Exchange adapter pattern
- All data routes through `get_exchange_adapter(ticker)` → `BaseExchangeAdapter`
- Circular imports are avoided via lazy (function-scope) imports inside adapter methods
- HK adapter: `_normalize_ticker()` pads bare codes to 4-digit `.HK` format
- New regions: add a `ConcreteAdapter` in `exchanges/`, register in `exchanges/__init__.py`

### Perplexity prefix quirk
The compiled JS hardcodes `/port/5000` as the API prefix. `_StripPerplexityPrefix`
middleware in `server.py` strips this before routing — do not remove that middleware.

---

## API contract (React frontend depends on these exactly — never change paths or field names)

| Method | Path | Key response fields |
|---|---|---|
| GET | `/api/quote/{ticker}` | price, changePercent, currency, currencySymbol |
| GET | `/api/realtime/{ticker}` | same as quote |
| GET | `/api/stock/{ticker}?range=` | bars: [{time,open,high,low,close,volume}] |
| GET | `/api/fundamentals/{ticker}` | marketCap, forwardPE, evToRevenue, evToEbitda, beta, revenue, revenueGrowth, grossMargin, operatingMargin, profitMargin, roe, targetPrice, currencySymbol, description, name, sector |
| GET | `/api/trials/{ticker}` | trials: [{nctId, title, phase, status, enrollment, …}] |
| GET | `/api/news/{ticker}` | [{title, publisher, publishedAt, url, summary}] |
| GET | `/api/confidence/{ticker}` | score (0–100), signal (BULLISH/BEARISH/NEUTRAL), factors, newsImpact |
| GET/POST | `/api/dcf/{ticker}` | impliedSharePrice, upside, currencySymbol, dcf:{…} |
| GET | `/api/scenarios/{ticker}` | currentPrice, currencySymbol, scenarios, monteCarlo |
| GET | `/api/search?q=` | quotes:[{symbol, shortname, exchange, quoteType}] |
| GET/POST/DELETE | `/api/watchlist[/{ticker}]` | array of ticker strings |

**New routes (to be added — React ignores unknown routes, so these are additive and safe):**
- `GET /api/filings/{ticker}` → [{date, title, type, url}]
- `GET /api/flow/{ticker}` → [{participant_id, participant_name, shares, percentage, snapshot_date}]
- `GET /api/pipeline-summary/{ticker}` → {summary: str, risks: [str], cached: bool}

---

## Development Roadmap

Work through phases in order. Phase 0 is the highest priority — it is a hard legal
requirement for the award (Rule 4: product must be in market ≥3 months before submission).

### Phase 0 — Deploy & Start the Clock (Complete ASAP)
**Files:** `server.py`, `requirements.txt`, new `railway.toml` or `Procfile`

- [ ] Add `X-API-Key` header authentication to all `/api/*` routes (env var: `API_KEY`)
      — public routes: `/`, `/assets/*`, `/api/docs`
- [ ] Add rate limiting via `slowapi`: 60 req/min per IP on all `/api/*` routes
- [ ] Restrict CORS: replace `allow_origins=["*"]` with the deployed domain
- [ ] Add input validation on all `{ticker}` path params: max 12 chars, `[A-Z0-9.\-]` only
- [ ] Deploy to Railway (or Render/fly.io): FastAPI + static files in one service, free HTTPS
- [ ] Record and save the live URL + exact deployment date as `DEPLOYMENT.md`
- [ ] Set env vars on host: `API_KEY`, `ENV=production`

**Award impact:** Unlocks Rule 4 eligibility. Lifts Quality score. Without this, no submission.

---

### Phase 1 — Complete the HK Adapter (Highest scoring impact per hour)
**Files:** `exchanges/hk.py`, `server.py`, `data_fetcher.py`

#### 1a. `get_trials()` — clinical pipeline for HK biotechs (1–2 days)
The US adapter already does this correctly. The HK adapter just needs to delegate:
```python
def get_trials(self, ticker: str) -> pd.DataFrame:
    from data_fetcher import fetch_clinicaltrials
    return fetch_clinicaltrials(self._normalize_ticker(ticker))
```
BeiGene (6160.HK), WuXi Biologics (2269.HK), Innovent (1801.HK), Hansoh (3692.HK) all
register trials on ClinicalTrials.gov under their English company names.

#### 1b. `get_filings()` — HKEXnews announcements (2–3 days)
Target: `https://www.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main_en.aspx`
Method: POST with `txtStockCode` = 4-digit code (e.g. `0700`), parse the HTML announcement table.
Return schema: `date, title, type, url`
Wire into server.py as `GET /api/filings/{ticker}`

#### 1c. `get_flow_data()` — CCASS shareholding snapshots (3–4 days)
Target: `https://www.hkexnews.hk/sdw/search/searchsdw.aspx`
Method: POST with `txtStockCode`, `ddlShareholdingDay/Month/Year`, `btnSearch=Search`
Fetch end-of-month snapshots for last 12 months. Concatenate into long-format DataFrame.
Return schema: `participant_id, participant_name, shares, percentage, snapshot_date`
Wire into server.py as `GET /api/flow/{ticker}`

**Award impact:** Functionality rises ~5 points. The HK market relevance criterion ("local
applicability, GBA opportunities") is now substantiated with real data, not stubs.

---

### Phase 2 — AI Upgrade (Innovation + "Best Use of AI" bonus)
**Files:** `server.py` (confidence route), new `llm_analysis.py`, `AI_GOVERNANCE.md`

#### 2a. LLM news sentiment (2–3 days)
Create `llm_analysis.py` with a `analyze_news_sentiment(headlines: list[str], ticker: str) -> dict` function.
- Use Anthropic Claude API (claude-sonnet-4-6 or claude-haiku-4-5 for cost)
- Batch all headlines in one call — system prompt is cacheable (use `cache_control: ephemeral`)
- Return: `{sentiment: "BULLISH"|"BEARISH"|"NEUTRAL", score: float, interpretation: str, key_events: [str]}`
- Replace the keyword regex block in `_build_confidence_payload()` in `server.py`
- Label all LLM outputs in the API response with `"ai_generated": true`

#### 2b. LLM pipeline risk summarization (1–2 days)
Add `summarize_pipeline(trials_df: pd.DataFrame, company_name: str) -> dict` to `llm_analysis.py`
- System prompt: biotech analyst persona, cacheable
- Input: top 5 active trials (title, phase, status, primary completion date)
- Output: `{summary: str, key_risks: [str], upcoming_catalysts: [str]}`
- Expose as `GET /api/pipeline-summary/{ticker}`

#### 2c. Document responsible AI governance
Create `AI_GOVERNANCE.md`:
- What data is sent to the LLM: headlines and trial titles only — no PII, no user data
- LLM outputs are clearly labeled as AI-generated in the API response
- RandomForest feature importances are exposed in `/api/confidence/{ticker}` (explainability)
- Model is retrained per request on the ticker's own history (no cross-user data leakage)
- Rate limiting prevents abuse of the LLM endpoint

**Award impact:** Innovation rises ~6 points. Opens "Best Use of AI" bonus category.

---

### Phase 3 — GBA & Cross-Border Features (Market Potential)
**Files:** `alpha_screener.py`, `utils.py`, `server.py`, new `dual_listing.py`

#### 3a. Dual-listing detection (1 day)
Create `dual_listing.py` with a `DUAL_LISTED` map:
```python
DUAL_LISTED = {
    "6160.HK": "BGNE",    # BeiGene
    "9688.HK": "ZLAB",    # Zai Lab
    "2359.HK": "WX",      # WuXi AppTec
    "BGNE":    "6160.HK",
    "ZLAB":    "9688.HK",
}
```
Add `GET /api/dual-listing/{ticker}` → returns the counterpart ticker, HK price, US price,
and premium/discount %. This is unique and directly addresses the cross-border criterion.

#### 3b. GBA biotech universe (half day)
Replace `DEFAULT_HK_UNIVERSE` in `alpha_screener.py` with the full GBA biotech set:
BeiGene (6160.HK), WuXi Biologics (2269.HK), WuXi AppTec (2359.HK), Innovent (1801.HK),
Hansoh (3692.HK), CSPC (1093.HK), Sino Biopharm (1177.HK), Zai Lab (9688.HK),
Legend Biotech (9987.HK), RemeGen (9995.HK), Shanghai Fosun Pharma (2196.HK).

#### 3c. Usage analytics (1 day)
Add a lightweight append-only log in `server.py`: each `/api/quote/{ticker}` hit writes
`{date, ticker, region}` to a JSONL file. No PII. This produces the adoption evidence
("X tickers analyzed in first N months") needed for the Market Potential criterion.

**Award impact:** Market Potential rises ~8 points. GBA and cross-border claims are
now feature-backed, not just narrative.

---

### Phase 4 — Security & Quality Hardening (Quality criterion)
**Files:** All modules, new `tests/` directory

- [ ] Pin all `requirements.txt` versions; run `pip-audit` for known CVEs
- [ ] Add structured request logging with request IDs (audit readiness)
- [ ] Add in-memory TTL cache for yfinance calls (60-second TTL; avoids duplicate upstream calls)
- [ ] Unit tests for `pipeline_analyzer.py` (phase normalisation, prob_approval values)
- [ ] Unit tests for `rnpv_calculator.py` (NPV math, scenario grid)
- [ ] Unit tests for `model.py` (feature shape, signal thresholds)
- [ ] Integration test: start server, hit `/api/quote/MRNA`, assert response shape

**Award impact:** Quality rises ~3 points.

---

### Phase 5 — Submission Documentation
**Files:** new `SUBMISSION/` directory

- [ ] Demo video (3 min): show BeiGene (6160.HK) full workflow — pipeline → CCASS flow →
      LLM sentiment → rNPV → dual-listing premium vs BGNE. This is the HK story.
- [ ] Screenshot evidence: deployment date, usage stats, clinical trial data, LLM output
- [ ] Narrative document: one section per judging criterion, weighted by score
      — Innovation: LLM + rNPV + cross-border uniqueness
      — Functionality: all 15+ API routes + HK adapter + new routes
      — Market Potential: deployment date + usage stats + GBA biotech market size
      — Impact: democratizing institutional tools for HK retail + small fund managers
      — Quality: auth, rate limiting, tests, governance doc
- [ ] `AI_GOVERNANCE.md` as supporting attachment
- [ ] HKIB positioning note: HKIB is the leading organiser — frame the submission around
      serving the community of HK banking/investment professionals that HKIB represents

---

## Coding standards

- Default: no comments unless the WHY is non-obvious
- No backwards-compatibility shims; just change the code
- Prefer editing existing files; only create new files when adding genuinely new modules
- All new API routes are additive only — never change existing route paths or response field names
  (the compiled React JS cannot be modified)
- New routes in `server.py` go BEFORE the static file mount (`app.mount("/assets", ...)`) and
  BEFORE the SPA fallback (`spa_fallback`)
- All yfinance calls go through `data_fetcher.py` primitives, not direct `yf.*` calls in
  `server.py` (keep the adapter layer intact)
- LLM calls go in `llm_analysis.py`, never inline in `server.py`
- Error handling: API routes return HTTP 502 on upstream failure, never 500 with traceback
- NaN/Inf in numeric responses: always sanitize via `_to_json_safe()` before returning JSON

## What NOT to do

- Do not modify `index.html` or anything under `assets/` — this is compiled output
- Do not change existing route paths or response field names
- Do not remove the `_StripPerplexityPrefix` middleware
- Do not add features beyond what the current phase requires
- Do not mock yfinance in tests — use real small fixtures (short price history CSVs)

---

## Dependencies

```
streamlit, yfinance, pandas, numpy, plotly, scikit-learn, requests, ta, scipy,
fastapi, uvicorn[standard], slowapi, anthropic
```

For deployment add: `gunicorn` (process manager) or let Railway use uvicorn directly.

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `API_KEY` | Shared API key for all `/api/*` routes | required in production |
| `ANTHROPIC_API_KEY` | Claude API for LLM analysis | required for Phase 2 |
| `ENV` | `development` or `production` | `development` |
| `LOG_LEVEL` | `INFO` or `DEBUG` | `INFO` |

In development (`ENV=development`), the API key check is skipped to allow local testing
without setting up credentials.
