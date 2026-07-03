# BioTerminal Pro — Full Product Audit

**Date:** 2026-07-02
**Method:** Static read of all backend/frontend source + live functional pass against a
locally-run `uvicorn server:app` (dev mode, no LLM keys set), probing every API route with
`MRNA`, `CRBU` (small clinical-stage), `6160.HK`, `0700.HK`, `9688.HK`, and edge cases
(`ZZZZZZ`, `AAPL`, `DROP;TABLE`, bare `700`). `pytest` run (84 passed). Frontend audited by
source read + confirming the canonical build compiles.
**Measuring stick:** would a pipeline-first, rNPV-literate biotech investor trust this every
morning, and would a learner be educated rather than misled? Award criteria noted, never
driving a verdict.

---

## 1. Executive verdict

**Would the target user adopt this today? No — not yet.** The plumbing is genuinely good:
real ClinicalTrials.gov data, working HKEXnews and CCASS scrapers (a real differentiator),
a clean windowed-desktop frontend, sane error handling, tests that pass. But the four
headline "analytics" a biotech investor would actually lean on — **DCF, rNPV, the ML
confidence signal, and the backtest** — are each capable of printing a confidently wrong
number with no visible caveat. For the trust bar this product sets ("Bloomberg-level"),
wrong-with-confidence is worse than missing.

**What breaks trust first (in order a real user would hit it):**

1. **rNPV is not this company's rNPV.** Every ClinicalTrials.gov row is treated as a separate
   drug worth a generic **$500M peak sales**, and the trial list itself contains false
   positives. `MRNA` produced **75 "assets"** (only 31 actually sponsored by Moderna; the rest
   include NIAID, NCI, an *"Aspirin in Preventing Recurrence of Cancer"* study, and a
   University of Oklahoma trial), the same drug counted many times over. The resulting
   "$599M pipeline rNPV / $1.51 per share / −98%" is noise dressed as a valuation.
2. **DCF prints fantasy numbers for exactly the companies this tool targets.** It seeds five
   years of growth from a single noisy yfinance `revenueGrowth` field and compounds it with no
   upper sanity bound. `MRNA` (revenue actually shrinking, −53% 3-yr CAGR) got a **DCF of
   $351.75 vs a $72.50 price — +385% "upside."** A small clinical-stage name with $11M of
   licensing revenue (`CRBU`) bypassed the rNPV fallback and got a **$0.06 DCF (−97%).**
3. **The ML "confidence signal" and backtest are decorative quant.** The model trains and
   "predicts" on the same overlapping windows with no holdout; the backtest is in-sample and,
   when it makes **zero trades**, still reports **"+38% alpha"** simply because the stock fell.
4. **The deployed UI is not the windowed desktop this audit calls canonical.** `server.py`
   serves the stale root `index.html` → `assets/index-KyStMcUq.js` (Jun 1), which has **no
   window manager, no pop-out, no "Quote Monitor" panel**. The new `frontend/src` desktop
   exists only in source and an un-shipped `frontend/dist`.
5. **"Add to watchlist" is broken** — the frontend POSTs to a route that returns **405**.

**Top 5 issues in plain language:** (1) rNPV counts random trials as $500M drugs; (2) DCF
gives absurd upside/downside for pre-revenue biotech; (3) ML signal + backtest are unvalidated
and can imply skill that isn't there; (4) the live site is running an old UI build; (5) the
watchlist add button does nothing.

**What's genuinely strong and worth protecting:** the HK data layer (HKEXnews filings + 12-month
CCASS shareholding, both scraping live sites successfully), the ClinicalTrials.gov integration
itself, the risk/devil's-advocate module (real, data-driven, honestly captioned), the phase
normalization + BIO/Informa probability mapping, and the overall engineering hygiene
(502-not-500 policy, `_to_json_safe`, TTL caches, request-id logging, ticker validation, 84
passing tests).

---

## 2. Route & panel inventory

27 API routes. Grades: **WORKS** / **DEGRADED** / **STUB** / **MISLEADING** / **BROKEN**.
Latencies from live probes (cold, dev mode, no LLM keys).

| Route | Consuming panel | Live result | Grade | One-line evidence |
|---|---|---|---|---|
| `GET /api/quote/{t}` | TopBar, Watchlist, Overview | `MRNA` $72.50, 1.1s | **WORKS** | Correct; but bare `700`→US data (see P2-bare) |
| `GET /api/realtime/{t}` | (polling) | alias of quote | **WORKS** | Literally `return get_quote()` |
| `GET /api/stock/{t}?range=` | ChartPane | all ranges → 1y daily | **DEGRADED** | `range=5D`→251 daily bars; casing mismatch, see P1-range |
| `GET /api/fundamentals/{t}` | Fundamentals, Overview | full dict, 0.5s | **WORKS** | Real yfinance fields; NaN→null handled |
| `GET /api/trials/{t}` | Pipeline, Overview, rNPV, Risk | `MRNA` 75 trials, 3.2s | **MISLEADING** | Includes non-sponsor false positives; `AAPL` returns trials |
| `GET /api/news/{t}` | News, Overview | 30 items, 0.4s | **WORKS** | Real headlines |
| `GET /api/confidence/{t}` | Confidence, Overview | score 50 NEUTRAL, 1.7s | **DEGRADED** | News factor inert w/o LLM; growth factor saturates; ML doesn't drive score |
| `GET/POST /api/dcf/{t}` | DCF, Overview | `MRNA` $351.75 (+385%) | **MISLEADING** | Compounds noisy growth, no upper clamp |
| `GET /api/rnpv/{t}` | rNPV | `MRNA` 75 assets @ $500M | **MISLEADING** | Trial=asset, generic peak sales, false positives |
| `GET /api/scenarios/{t}` | Scenarios | base −36.8%, 0.1s | **DEGRADED** | Fixed 25/50/25 probs; base from stale analyst target |
| `GET /api/search?q=` | TickerInput | BeOne/BeiGene, 0.3s | **WORKS** | yfinance search |
| `GET /api/watchlist` | Watchlist | array, 0.0s | **WORKS** | Reads JSON file |
| `POST /api/watchlist` | — (not called by UI) | 200 w/ body | **WORKS** | But UI never hits this shape |
| `POST /api/watchlist/{t}` | Watchlist "add" | **405** | **BROKEN** | Frontend `addToWatchlist` POSTs here; no such route |
| `DELETE /api/watchlist/{t}` | Watchlist "remove" | 200 | **WORKS** | Matches frontend |
| `GET /api/dual-listing/{t}` | DualListing | `9688`→ZLAB ok; `6160`→"delisted" | **MISLEADING** | Hardcoded map; BeiGene "delisted Aug 2024" is factually wrong |
| `GET /api/pipeline-summary/{t}` | (Pipeline AI) | "Insufficient trial data" | **STUB** | No LLM key → default; message misattributes cause |
| `GET /api/pipeline-research/{t}` | Pipeline (AI view) | "unavailable — set API key" | **STUB** | Entire AI pipeline feature needs a key none set |
| `GET /api/debug/llm` | — (diagnostic) | all keys NOT SET | **WORKS** | Honest diagnostic |
| `GET /api/filings/{t}` | Filings | `6160` 11 real filings, 5s | **WORKS** (HK) / **DEGRADED** (US) | US returns news labeled "News"; `type` field dirty w/ HTML entities |
| `GET /api/flow/{t}` | CCASS | `6160` 1765 rows/11 months, **38.6s** | **WORKS** (HK) / **STUB** (US) | Real CCASS; US 13F returns `[]`; first load painfully slow |
| `GET /api/sources/{t}` | (links) | curated URLs, 0.0s | **WORKS** | Deep links build correctly |
| `GET /api/backtest/{t}` | Backtest | 0 trades, "+38% alpha" | **MISLEADING** | In-sample; alpha vs buy-hold with no trades |
| `GET /api/screen?region=` | Screener | US 11.5s / HK 16.8s | **WORKS** (w/ caveats) | Real ranking; dimension names oversell (see engine verdicts) |
| `GET /api/risk/{t}` | Risk, Overview | `MRNA` 3 factors MEDIUM, 3.2s | **WORKS** | Data-driven; one boilerplate regulatory factor |
| `GET /api/earnings/{t}` | Earnings | targets ok, EPS often empty | **DEGRADED** | `nextEarningsDate` null, quarterly EPS frequently empty via yfinance |
| `GET /{full_path}` (SPA) | — | serves stale index.html | **DEGRADED** | Serves the old pre-window bundle |

**Panels (16) vs routes:** every panel maps to a route. Notable frontend gaps:
- **Watchlist "add"** calls a 405 route → dead button.
- **Chart range selector** (`1D/1W/1M/3M/1Y/5Y`) is decorative — server only matches lowercase
  `1d/5d/1mo/...`, so every button yields ~1 year of daily bars.
- **Pipeline AI view / pipeline-summary / news sentiment** all silently degrade to empty/neutral
  without an LLM key — in this environment (and by default) they contribute nothing.
- No route is entirely unused by a panel; `POST /api/watchlist` (body form) is the one handler
  the UI never calls in the shape it expects.

---

## 3. Ranked findings

### P0 — Trust-breakers (wrong or misleading output)

**P0-1 · rNPV treats every trial as a distinct $500M drug, on a false-positive trial list.**
`rnpv_calculator.pipeline_rnpv()` iterates the trials DataFrame one row = one asset
([rnpv_calculator.py:177](rnpv_calculator.py#L177)) using `AssetAssumptions` defaults
(`peak_sales=$500M`, [rnpv_calculator.py:64](rnpv_calculator.py#L64)). The trial list comes from
`fetch_clinicaltrials` which searches CT.gov by `query.term` as well as `query.spons`
([data_fetcher.py:316](data_fetcher.py#L316)), pulling in trials the company doesn't own.
*Repro:* `/api/rnpv/MRNA` → 75 assets, each Phase-3 → $500M → $300M net rNPV, including
*"Aspirin in Preventing Recurrence of Cancer"* and NCI/NIAID studies; the same drug
(`mRNA-1010`) appears multiple times. **Impact:** the headline valuation of the app's marquee
biotech feature is meaningless and will be obviously wrong to any analyst. **Fix:** dedupe to
drug/program level, restrict to lead-sponsor trials, and require per-asset peak-sales input
(or at minimum a phase/indication-based estimate) instead of a flat $500M.

**P0-2 · DCF produces absurd values for pre-/low-revenue biotech.**
`_default_assumptions` seeds Y1–Y5 growth from one yfinance `revenueGrowth` value and only
floors it at −0.5, never caps it ([server.py:696](server.py#L696)); `_run_dcf` compounds it
([server.py:659](server.py#L659)). *Repro:* `/api/dcf/MRNA` → growth path 260%→104%,
**implied $351.75 vs $72.50 = +385%** for a company whose revenue is falling; `/api/dcf/CRBU`
(≈$11M licensing revenue) → **$0.06 (−97%)**. The rNPV fallback only triggers at
`revenue <= 0` ([server.py:640](server.py#L640)), so anything with a sliver of revenue gets the
broken DCF. **Impact:** a learner is actively miseducated (DCF is the wrong tool here and the
number is nonsense); a pro loses trust instantly. **Fix:** gate DCF on positive *and* growing
FCF; route clinical-stage/negative-margin names to rNPV; clamp implied upside and surface the
growth assumptions used.

**P0-3 · "ML confidence signal" is unvalidated in-sample fit.**
`build_training_dataset` builds one sample per day with stride 1 and a 20-day forward label
([model.py:119](model.py#L119)); `_train_and_predict` fits on all ~400 heavily-autocorrelated
rows and predicts the current row with **no train/test split or walk-forward**
([model.py:202](model.py#L202)). `confidence = |bull_prob − 0.5|·2` is forest vote dispersion,
not measured accuracy. *Repro:* `/api/confidence/MRNA` → `mlSignal BULLISH, bullProb 0.66,
trainedOn 421`. **Impact:** presenting this as an "ML confidence signal" implies predictive
skill that has never been tested out-of-sample. **Fix:** add walk-forward validation and report
realized hit-rate; relabel as a technical-momentum classifier, not "confidence"; or demote to
clearly-experimental.

**P0-4 · Backtest reports alpha for a strategy that never traded, in-sample only.**
`run_backtest` has no out-of-sample split; `_calc_metrics` computes `alpha_pct = total_return −
bh_return` ([backtester.py:205](backtester.py#L205)). *Repro:* `/api/backtest/MRNA` →
`n_trades: 0, total_return: 0%, bh_return: −38%, alpha: +38%`. **Impact:** implies the strategy
"beat the market by 38%" when it did nothing but sit in cash during a decline; commission is
modeled but survivorship/in-sample bias is not disclosed. **Fix:** suppress or flag alpha when
`n_trades==0`, add a walk-forward or at least an explicit "in-sample, single-ticker" disclaimer,
and show trade count prominently.

**P0-5 · Dual-listing states a corporate action that appears to be false.**
`DELISTED_ADS` hardcodes *"BeiGene voluntarily delisted its US ADS from NASDAQ in August 2024"*
([dual_listing.py:33](dual_listing.py#L33)). BeiGene did not delist from Nasdaq in 2024; it
rebranded to **BeOne Medicines** (ticker `BGNE`→`ONC`) — the app's own `/api/search` returns
"BeOne Medicines Ltd" and `/api/sources` shows "BeOne Medicines AG". *Repro:*
`/api/dual-listing/6160.HK` → `status:"delisted", us_ticker:"BGNE", note:"...delisted...August
2024"`. **Impact:** presents fabricated or stale corporate-action history as fact on the flagship
HK ticker. **Fix:** verify each entry against a live source and date-stamp it; drive
dual-listing status from data, not a hand-maintained dict.

### P1 — Broken / stub

**P1-1 · Watchlist "add" button is dead (405).** `addToWatchlist` POSTs
`/api/watchlist/{ticker}` ([frontend/src/api.ts:37](frontend/src/api.ts#L37)); the server only
defines `POST /api/watchlist` (body) and `DELETE /api/watchlist/{ticker}`
([server.py:872](server.py#L872)). *Repro:* `POST /api/watchlist/TESTX` → **405**. The UI
swallows the error and re-loads the unchanged list, so the button appears to do nothing.
**Fix:** add `POST /api/watchlist/{ticker}` or change the client to POST the body form.

**P1-2 · Chart range selector does nothing.** Frontend sends `1D/1W/1M/3M/1Y/5Y`
([frontend/src/tabs/OverviewTab.tsx:10](frontend/src/tabs/OverviewTab.tsx#L10)); server maps
only lowercase `1d/5d/1mo/3mo/6mo/1y/2y/5y/max` ([server.py:273](server.py#L273)), so every
selection falls through to the `1y`/`1d` default. *Repro:* `range=5D` → 251 daily bars.
**Impact:** clicking "1D" shows a year of daily candles; the intraday intervals are never
used. **Fix:** normalize case / map the UI labels to periods.

**P1-3 · All LLM features are non-functional by default.** `/api/pipeline-research`,
`/api/pipeline-summary`, and the News-Sentiment factor inside `/api/confidence` return
empty/neutral without a key; `/api/debug/llm` confirms none set. The Pipeline tab's headline
"AI-powered pipeline research with TAM" and the confidence "News Sentiment" factor therefore
contribute nothing in this environment. **Impact:** the "Best Use of AI" story and the most
differentiated pipeline view are dark unless a key is present on the host. **Fix:** confirm the
Railway deploy has a key; make the degraded state explicit in the UI ("AI unavailable"), and
fix the `pipeline-summary` message that blames "insufficient trial data" when the real cause is
a missing key.

**P1-4 · US institutional flow is an empty stub.** `USExchangeAdapter.get_flow_data` returns an
empty DataFrame ([exchanges/us.py:102](exchanges/us.py#L102)); `/api/flow/MRNA` → `[]`. The
CCASS tab is HK-only by design, but a US ticker in that panel dead-ends silently.

### P2 — Missing table-stakes for the target user

**P2-1 · No cash / burn / runway on the main surface.** The single most important biotech metric
is computed only *inside* the risk module ([devils_advocate.py:81](devils_advocate.py#L81)) and
never surfaced as a first-class number. `fundamentals` returns `cash`/`totalDebt` but no burn or
runway. **Table-stakes.**

**P2-2 · No catalyst calendar.** Primary-completion dates exist per trial and
`upcoming_catalysts()` is implemented ([pipeline_analyzer.py:91](pipeline_analyzer.py#L91)) but
there is no PDUFA/AdComm/readout calendar view. **Table-stakes** for a catalyst-driven user.

**P2-3 · Trial depth is shallow.** No endpoints, comparators/arms, or enrollment-vs-plan; the
Pipeline table shows title/phase/status/enrollment only. **Differentiator gap.**

**P2-4 · Bare HK code returns US data on most routes.** Routes that call
`df_mod._cached_yf_info(ticker)` directly (quote, fundamentals, scenarios, dcf, confidence)
never invoke the adapter's `_normalize_ticker`, so `700` is sent raw to yfinance. *Repro:*
`/api/quote/700` → **$429.80 USD** (a US instrument), while `/api/quote/0700.HK` → HK$431.
**Fix:** normalize tickers at the server boundary, not just inside the adapter.

**P2-5 · Absent:** short interest, insider transactions, 13F ownership, dilution/ATM/shelf
history, patent/exclusivity cliffs, peer-comps table, export/share (CSV/PDF/permalink).

### P3 — UX friction

- **CCASS first load ~38s** ([exchanges/hk.py:201](exchanges/hk.py#L201)) with only a spinner —
  feels hung; cached 1h after. Consider progressive/streamed months or a "still loading" note.
- **Filings `type` field is dirty** — HTML entities (`&#x2f;`) and run-on "…More" text leak
  through ([exchanges/hk.py:164](exchanges/hk.py#L164)).
- **Scenarios base case can read below the current price** (from stale analyst `targetMean`),
  making "Base −36.8% / Bull +9%" look incoherent without explanation.
- **Non-biotech tickers return "trials"** (`AAPL` → Apple Watch arrhythmia studies) with no
  "this may not be a biotech" signal.
- **Invalid ticker returns 200 with null price** rather than a clear not-found state.

### P4 — Polish

- `app.py` (Streamlit) is dead weight; `requirements.txt` still pins `streamlit`, `plotly`, `ta`.
- `datetime.utcnow()` deprecation warnings ([server.py:205](server.py#L205)).
- `data_fetcher.get_peers` is a hardcoded stub with a `TODO`.
- `_default_confidence` omits `mlSignal`, so the neutral fallback response shape differs subtly
  from the success shape.
- CLAUDE.md is materially stale (see §7).

---

## 4. Analytical integrity verdicts

| Engine | Verdict | Reasoning |
|---|---|---|
| **rNPV** (`rnpv_calculator.py`) | **MISLEADING** | Phase probabilities are sound (BIO/Informa, correctly cumulative incl. combo phases). But it values every CT.gov row as an independent $500M drug on a false-positive-laden trial list; no per-asset peak sales, no dedupe, no use of the company's *actual* disclosed pipeline. Assumptions ($500M/10% WACC/12y/35%) are shown in the tab footer — good — but they're applied uniformly, which is the core defect. |
| **DCF** (`server.py`) | **MISLEADING** | Incoherent for the target universe. Growth seeded from one noisy yfinance field and compounded with no upper bound; rNPV fallback only at zero revenue. Sliders are honest and interactive, but the default output is untrustworthy (MRNA +385%, CRBU −97%). |
| **RandomForest** (`model.py`) | **DECORATIVE** | No lookahead leakage in features (windows are `:i`), and it honestly excludes fundamentals to avoid it — credit there. But no train/test/walk-forward, stride-1 overlapping samples, and "confidence" = vote dispersion, not validated accuracy. Presented as an "ML confidence signal" it overstates rigor. It correctly does *not* drive the headline score. |
| **Backtester** (`backtester.py`) | **MISLEADING** | Commissions modeled (good), but in-sample, single-ticker, no out-of-sample, and reports positive alpha even with zero trades. Overstates strategy quality. |
| **Monte Carlo** (`scenarios`) | **SOUND-WITH-CAVEATS** | GBM from realized 1y daily vol × clamped beta, seeded (reproducible), overflow-guarded. Reasonable as an illustrative cone; caveat: drift = 0 and vol is naive, so it's a volatility fan, not a forecast — not labeled as such. |
| **Confidence score** (`server.py`) | **SOUND-WITH-CAVEATS** | Transparent weighted 5-factor composite with weights exposed. Caveats: Growth factor saturates on a single noisy yfinance number (MRNA → 100), News factor is inert without an LLM key (always 50), and the composite's meaning ("weighted sum of heuristics") isn't explained to the user. Not keyword-regex anymore (CLAUDE.md is stale on this). |
| **Alpha screener** (`alpha_screener.py`) | **SOUND-WITH-CAVEATS** | Runs, ranks, real data across a good GBA universe. But dimension names oversell: "Value" is P/S+EV/Rev only (meaningless for pre-revenue), "Quality" rewards cash/mktcap and revenue growth (a cash-burner can score 20/20), "Pipeline" is phase-weighted active-trial count on the same false-positive trial list. Directionally useful, not literally what the labels claim. |
| **Devil's advocate** (`devils_advocate.py`) | **SOUND** | The best engine. Real per-company checks (runway, debt/mktcap, no-Phase-3, single-asset concentration, death cross, drawdown, rich multiples), severity-scored, evidence-cited, honestly captioned as a systematic bear case, not a recommendation. Only the generic "binary FDA event risk" factor is boilerplate for anything with a trial. |

---

## 5. Coverage gap map

| Capability | Status | Priority for target user |
|---|---|---|
| Cash / burn / **runway** | **partial** (buried in Risk only) | **table-stakes** |
| Dilution / ATM / shelf registrations | **absent** | table-stakes |
| **Catalyst calendar** (readouts, PDUFA, AdComm) | **absent** (dates exist per-trial) | **table-stakes** |
| Trial depth (endpoints, comparators, enroll vs plan) | **partial** (title/phase/status/enroll) | differentiator |
| Competitive landscape per indication | **partial** (only via LLM pipeline-research, key-gated) | differentiator |
| Short interest / insider / 13F ownership | **absent** (US flow stub) | differentiator |
| Patent / exclusivity cliffs | **absent** | differentiator |
| Peer comps table | **absent** (hardcoded `get_peers` stub) | table-stakes |
| CCASS institutional flow (HK) | **present** (real, 12-month) | **differentiator ✓** |
| HKEXnews filings (HK) | **present** (real) | **differentiator ✓** |
| Dual-listing premium/discount | **partial** (2 live pairs; 1 inaccurate delisted entry) | differentiator |
| Watchlist (alerts, positions) | **partial** (bare list; add is broken) | optional |
| Export / sharing (CSV/PDF/permalink) | **absent** | optional |
| **Learner support** (what rNPV/phase-prob mean) | **partial** | table-stakes for the learner persona |

On learner support: the rNPV tab has a genuinely good "What is rNPV?" explainer and a phase-prob
reference; the risk tab is well-captioned. But DCF, the confidence composite, the ML signal, and
the backtest present raw numbers with no explanation of what they mean or how much to trust them —
which, given P0-2/3/4, actively misleads the learner.

---

## 6. Quality & security snapshot

- **Auth:** `X-API-Key` middleware exists but is **skipped entirely in dev** and bypassed for any
  request whose `Referer` matches the host or path starts with `/port/5000/`
  ([server.py:93](server.py#L93)) — i.e. the browser SPA never needs a key. Reasonable for a
  public read-only tool; means the key protects nothing against a scripted client that sets a
  `Referer`. Fine for this threat model, worth noting.
- **CORS:** defaults to `*` unless `CORS_ORIGINS` set ([server.py:149](server.py#L149)).
- **Rate limiting:** slowapi 60/min/IP wired globally ([server.py:63](server.py#L63)). Present.
- **Input validation:** ticker regex `^[A-Z0-9.\-]{1,12}$` enforced by middleware;
  `DROP;TABLE` → 400 confirmed. Good (and no SQL anywhere, so low risk regardless).
- **Secrets in errors:** `_safe_err` strips `?key=` from messages; `/api/debug/llm` masks keys.
  Good. But upstream routes `raise HTTPException(status_code=502, detail=str(exc))` — the
  502-not-500 policy holds, though raw exception text is still returned to the client.
- **Tests:** 84 pass in ~8s. They cover engine *mechanics* (phase normalization, rNPV math,
  model feature shape, one live `/api/quote/MRNA` integration check) — **not** the trust defects
  above. No test asserts CT.gov sponsor correctness, DCF sanity bounds, or out-of-sample model
  behavior. Coverage of "what matters for trust" is effectively zero.
- **Logging:** per-request id + duration middleware present; clean.
- **Error consistency:** `_to_json_safe` used consistently; NaN/Inf handled; most routes degrade
  to empty payloads rather than 500s.

---

## 7. CLAUDE.md drift (doc vs reality)

- Claims sentiment is "keyword regex; no LLM" — **false**, it's LLM (Claude Haiku) with a
  no-key neutral fallback ([server.py:492](server.py#L492)).
- Claims HK `get_trials`/`get_flow_data`/`get_filings` "all return empty DataFrames" — **false**,
  all three are implemented and working live (trials delegate to CT.gov; filings + CCASS scrape
  successfully).
- Lists `llm_analysis.py`, `dual_listing.py`, `tests/`, and the rnpv/backtest/screener/risk/
  earnings/filings/flow routes as not-yet-built — **all exist**.
- Roadmap Phase 0/1 items (deploy, auth, rate limit, validation, HK adapter) are **done**.
- Primary interface is described as the pre-compiled SPA; the **canonical windowed UI in
  `frontend/src` is not the bundle `server.py` actually serves** — the served
  `assets/index-KyStMcUq.js` predates the window manager, pop-out, and "Quote Monitor" panel.
  `frontend/dist` (freshly built, has those markers) is not copied to root/`assets`.

---

## 8. Proposed roadmap (ordered by trust-impact per effort)

Each phase has a testable deliverable. No product code changed during this audit.

**Phase A — Ship the real UI + fix dead controls (0.5 day, pure trust/visibility).**
Copy `frontend/dist` → root `index.html`+`assets/` (or point `server.py` at `frontend/dist`);
add `POST /api/watchlist/{ticker}`; map the chart range labels to periods.
*Deliverable:* served bundle contains `win-drag`/`windows.v1`/`popout`; `POST
/api/watchlist/X`→200; `range=1D` returns intraday bars.

**Phase B — Stop the analytics from lying (2–3 days, highest trust impact).**
(1) rNPV: dedupe trials to program level, restrict to lead-sponsor, require/estimate per-asset
peak sales. (2) DCF: gate on positive+growing FCF, cap growth, route clinical-stage to rNPV,
show assumptions. (3) Backtest: hide alpha when `n_trades==0`, add in-sample disclaimer. (4) ML:
add walk-forward validation + realized hit-rate, or relabel as "technical momentum" and mark
experimental. *Deliverable:* `MRNA` rNPV lists ~Moderna programs (not 75 rows incl. aspirin);
`MRNA` DCF no longer prints +385%; backtest with 0 trades shows no alpha; confidence tab reports
a measured accuracy number.

**Phase C — Fix data-integrity edges (1 day).**
Normalize tickers at the server boundary (bare `700`→`0700.HK` everywhere); clean the filings
`type` field; verify/date-stamp the dual-listing map (correct the BeiGene entry); add a
"not a biotech / no sponsor match" signal when trials are collaborator-only. *Deliverable:*
`/api/quote/700`==`/api/quote/0700.HK`; dual-listing facts cite a source.

**Phase D — Close a table-stakes gap: runway + catalyst calendar (2–3 days).**
Surface cash/burn/runway as first-class fields; build a catalyst calendar from existing
primary-completion dates + PDUFA where available. *Deliverable:* a Runway number on the overview
and a sorted upcoming-catalyst list per ticker.

**Phase E — Make the AI real and honest (1–2 days).**
Confirm the deployed host has an LLM key; render an explicit "AI unavailable" state instead
of silent neutral; fix the `pipeline-summary` no-key message. *Deliverable:* `/api/debug/llm`
green on the deploy; degraded state visible in-UI.

**Phase F — Trust-focused tests (1 day).**
Add tests that assert CT.gov results are lead-sponsor for a known ticker, DCF stays within sane
bounds for a declining-revenue name, and the backtest suppresses alpha at 0 trades.
*Deliverable:* red tests today, green after Phases B–C.

---

*End of audit. No product code was modified. Awaiting sign-off on the roadmap before any change.*
