# BioTerminal Pro — HKICTA 2026 Submission Narrative
**Category:** Emerging FinTech (Non-Web3)
**Applicant:** Kyle Hui (Hong Kong resident, individual)
**Live URL:** https://web-production-cc55d.up.railway.app
**Deployment date:** 2026-05-28 (≥ 3 months before submission — satisfies Rule 4)

---

## Executive Summary

BioTerminal Pro is a Bloomberg Terminal-style investment research platform built
specifically for Hong Kong and Greater Bay Area (GBA) biotech investors. It delivers
institutional-grade analysis — clinical trial pipelines, risk-adjusted valuations,
ML confidence signals, LLM-powered sentiment, and real-time cross-border
premium/discount tracking — through a free, publicly accessible web interface.

The platform addresses a structural gap in Hong Kong's retail and small-fund investment
ecosystem: the tools used by professional biotech analysts (pipeline databases, rNPV
models, CCASS flow data, and NLP-driven news analysis) are either unavailable to
individuals or prohibitively expensive (Bloomberg Terminal: ~HK$190,000/year).
BioTerminal Pro makes this analysis accessible to the HKIB community and the broader
base of HK banking and investment professionals it represents.

---

## 1. Innovation & Creativity (30%)

### 1a. LLM-Powered News Sentiment (Claude API)
BioTerminal Pro replaces conventional keyword-based sentiment analysis with a
production-integrated Anthropic Claude AI pipeline. When a user queries any biotech
ticker, the system:

1. Fetches the 15 most recent news headlines
2. Submits them in a single batched prompt to Claude (Haiku 4.5), with the biotech
   analyst system prompt cached using `cache_control: ephemeral` to minimise latency
   and cost
3. Returns a structured JSON response: `sentiment (BULLISH/BEARISH/NEUTRAL)`,
   `score (-1.0 to +1.0)`, `interpretation (plain-English rationale)`,
   `key_events (top 3 market-moving headlines)`

All LLM outputs are labelled `"ai_generated": true` in the API response, ensuring
full transparency to end users. This is not a prototype — it runs in production on
every confidence request.

### 1b. Risk-Adjusted NPV (rNPV) Pipeline Valuation
The platform implements a quantitative rNPV model using BIO/Informa 2023 industry
phase-transition probabilities:

| Phase | P(approval from this phase) |
|---|---|
| Phase 1 | 7.3% |
| Phase 2 | 14.0% |
| Phase 3 | 49.1% |
| NDA/BLA | 85.3% |

For each active clinical trial retrieved from ClinicalTrials.gov, the model computes:
`rNPV = P(approval) × NPV_of_peak_sales_cashflows − PV_of_development_costs`

This is the same valuation methodology used by institutional biotech analysts and
documented in academic literature (BIO/Informa, 2023; Stewart et al., Nature Reviews
Drug Discovery, 2018). The full 3×3 scenario grid (bear/base/bull peak sales ×
low/mid/high discount rate) is exposed via the API for sensitivity analysis.

### 1c. Real-Time Cross-Border Premium/Discount Tracking
BioTerminal Pro is the only publicly available tool that computes live HK/US
premium-discount for GBA biotech dual-listings, accounting for ADS ratios:

- **Zai Lab:** 9688.HK ↔ ZLAB (1 ADS = 10 ordinary shares)
- **HUTCHMED:** 0013.HK ↔ HCM (1 ADS = 5 ordinary shares)

Example: Zai Lab (9688.HK) currently trades at **-2.2% discount** to its NASDAQ ADS
equivalent. This cross-border arbitrage signal is uniquely relevant to GBA investors
navigating both the HKEX and US markets simultaneously.

### 1d. ClinicalTrials.gov Integration for HK Biotechs
The platform resolves HK ticker symbols (e.g., `6160.HK` → "BeiGene") and
automatically queries ClinicalTrials.gov by company name, bringing US-standard
clinical trial transparency to HK-listed biotechs that register trials globally.

### 1e. CCASS Shareholding Flow Data
Twelve months of end-of-month CCASS (Central Clearing and Settlement System)
snapshots are retrieved and exposed for any HK-listed biotech. This institutional
ownership flow data — previously accessible only via manual HKEX website searches
— is surfaced programmatically for the first time in a free tool.

---

## 2. Functionality (25%)

### 2a. Live API — 18 Endpoints

| Endpoint | Function |
|---|---|
| `GET /api/quote/{ticker}` | Live price, change %, currency |
| `GET /api/realtime/{ticker}` | Same as quote (polled by frontend) |
| `GET /api/stock/{ticker}?range=` | OHLCV bars (9 timeframes, 6 intervals) |
| `GET /api/fundamentals/{ticker}` | 25 fundamental metrics |
| `GET /api/trials/{ticker}` | ClinicalTrials.gov pipeline with rNPV enrichment |
| `GET /api/news/{ticker}` | 30 recent headlines with summaries |
| `GET /api/confidence/{ticker}` | ML signal + LLM sentiment + 5 factor scores |
| `GET /api/dcf/{ticker}` | DCF intrinsic value (GET defaults, POST custom) |
| `POST /api/dcf/{ticker}` | DCF with custom assumptions |
| `GET /api/scenarios/{ticker}` | 3-scenario model + 1,000-path Monte Carlo |
| `GET /api/search?q=` | Ticker search |
| `GET /api/watchlist` | Persistent watchlist |
| `POST /api/watchlist` | Add to watchlist |
| `DELETE /api/watchlist/{ticker}` | Remove from watchlist |
| `GET /api/filings/{ticker}` | HKEXnews announcements (HK) / news proxy (US) |
| `GET /api/flow/{ticker}` | CCASS 12-month shareholding snapshots |
| `GET /api/dual-listing/{ticker}` | Cross-border premium/discount |
| `GET /api/pipeline-summary/{ticker}` | LLM pipeline risk summary |

### 2b. HK Exchange Adapter
A complete exchange adapter for HKEX-listed equities:
- Ticker normalisation (bare codes → `0700.HK` 4-digit format)
- Price and fundamental data via yfinance
- Clinical trials via ClinicalTrials.gov (company name lookup)
- Announcements via HKEXnews advanced search scraper (ASP.NET form)
- CCASS shareholding via HKEX SDW scraper (12 months × end-of-month, 3 parallel workers)

### 2c. GBA Biotech Universe
The alpha screener covers 13 GBA-listed biotechs:
BeiGene, WuXi Biologics, WuXi AppTec, Innovent Biologics, Hansoh Pharma,
CSPC Pharmaceutical, Sino Biopharmaceutical, Zai Lab, RemeGen, CStone,
CanSino Biologics, Shanghai Fosun Pharma, HUTCHMED.

---

## 3. Market Potential (25%)

### 3a. Live Deployment
BioTerminal Pro has been publicly available at
**https://web-production-cc55d.up.railway.app** since **2026-05-28**.

Usage statistics (update before submission):
- Total tickers analysed: **[X]**
- Unique tickers: **[X]**
- HK tickers analysed: **[X]** ([X]% of total)
- Days since launch: **[X]**

*Source: `usage_log.jsonl` — append-only log recording {date, ticker, region} for
every quote request. No PII collected.*

### 3b. Addressable Market
The GBA biotech sector represents a significant and growing investment universe:

- **HKEX biotech listings:** 70+ listed biotech companies (HKEX Main Board Chapter
  18A and dual-primary listings) with combined market capitalisation exceeding
  HK$1 trillion
- **GBA initiative:** The Guangdong-Hong Kong-Macao Greater Bay Area is home to
  China's largest biotech cluster, with the Hong Kong government investing HK$3
  billion in the InnoHK initiative targeting life sciences
- **Retail investor gap:** Hong Kong has 1.3 million active retail brokerage accounts
  (SFC Annual Report 2024). None have access to Bloomberg-grade pipeline analysis
  without institutional affiliation

### 3c. Target Users
1. **HK retail investors** with biotech holdings on HKEX
2. **Small and mid-size fund managers** in Hong Kong without Bloomberg subscriptions
3. **HKIB members** — equity research analysts, buy-side analysts, and investment
   managers who need rapid pipeline assessment for HK biotech positions
4. **GBA cross-border investors** navigating simultaneous HK and US listings

### 3d. Alignment with HK FinTech Strategy
BioTerminal Pro directly supports the HKMA's FinTech 2025 strategy objective of
"data-driven financial services" and the SFC's recognition of AI-powered investment
tools as a key innovation category (SFC Consultation Paper on AI in Asset Management,
2025).

---

## 4. Benefits & Impact (10%)

### 4a. Democratising Institutional Research
The core value proposition is accessibility. The analysis delivered by BioTerminal Pro
is structurally equivalent to what institutional analysts perform manually using:
- FactSet / Bloomberg (pipeline data): HK$120,000–190,000/year
- ClinicalTrials.gov manual searches: hours per company
- Excel-based rNPV models: bespoke per analyst

BioTerminal Pro delivers this in seconds, for free, for any HKEX or NASDAQ-listed
biotech.

### 4b. Cross-Border Transparency
The HK/US premium-discount feature makes a previously opaque price relationship
explicit for retail investors. When Zai Lab (9688.HK) trades at a discount to ZLAB,
HK retail investors are disadvantaged relative to US institutional investors who
monitor this spread automatically. BioTerminal Pro corrects this information asymmetry.

### 4c. Responsible AI in Finance
Unlike many AI-powered financial tools that present LLM outputs as facts,
BioTerminal Pro explicitly labels every AI-generated field (`"ai_generated": true`),
provides a plain-English interpretation alongside numeric scores, and documents its
full AI governance policy in `AI_GOVERNANCE.md`. This positions the platform at the
forefront of responsible AI deployment in HK financial services.

---

## 5. Quality (10%)

### 5a. Security
- **Authentication:** `X-API-Key` header required on all `/api/*` routes in production
- **Rate limiting:** 60 requests/minute per IP via `slowapi`
- **Input validation:** Ticker symbols validated against `[A-Z0-9.\-]{1,12}` regex;
  injection-style inputs return HTTP 400
- **CORS:** Restricted to deployed domain in production
- **Dependency audit:** `pip-audit` clean — all 3 CVEs patched at time of submission
  (CVE-2026-25645, CVE-2026-34450, CVE-2026-34452)
- **Pinned dependencies:** All `requirements.txt` versions exact-pinned (`==`)

### 5b. Test Coverage — 64 Tests Passing
| Test file | Tests | Coverage |
|---|---|---|
| `test_pipeline_analyzer.py` | 27 | Phase normalisation (17 parametrized), prob_approval math, enrich_trials |
| `test_rnpv_calculator.py` | 13 | NPV math correctness, scenario grid shape and ordering |
| `test_model.py` | 14 | Feature shape, training dataset, signal/confidence invariants |
| `test_integration.py` | 10 | Live API shape, 400 validation, dual-listing, headers |

### 5c. Observability
- Structured request logging: `rid / method / path / status / duration_ms` per request
- `X-Request-Id` response header for request tracing
- `usage_log.jsonl`: append-only adoption evidence (no PII)

### 5d. AI Governance
Full governance documentation in `AI_GOVERNANCE.md`:
- What data is sent to the LLM (headlines and trial titles only — no PII)
- Transparency labelling (`ai_generated` field in all responses)
- Explainability (factor scores and feature importances exposed in confidence API)
- Privacy (no user accounts, no tracking, no PII in logs)
- Rate limiting and abuse prevention

---

## Supporting Attachments

1. `AI_GOVERNANCE.md` — AI data usage, labelling, and governance policy
2. `DEPLOYMENT.md` — Live URL and deployment date (Rule 4 evidence)
3. `SUBMISSION/03_demo_script.md` — Script for the 3-minute demo video
4. `SUBMISSION/04_api_reference.md` — Complete API reference (18 endpoints)
5. Demo video: `SUBMISSION/demo_video.mp4` *(to be recorded)*
6. Screenshots: `SUBMISSION/screenshots/` *(to be captured)*
