# BioTerminal Pro — API Reference (18 Endpoints)

Base URL: `https://web-production-cc55d.up.railway.app`

All `/api/*` endpoints require `X-API-Key` header in production.
Public routes: `GET /`, `GET /api/docs`, static assets.

---

## Price & Market Data

### `GET /api/quote/{ticker}`
Live price, daily change, and currency.
```json
{"price": 47.64, "changePercent": 0.013, "currency": "USD", "currencySymbol": "$"}
```

### `GET /api/realtime/{ticker}`
Identical to `/api/quote` — polled every 30 seconds by the frontend.

### `GET /api/stock/{ticker}?range={range}`
OHLCV bars. `range` values: `1d 5d 1mo 3mo 6mo 1y 2y 5y max`
```json
{"bars": [{"time": "2026-05-27", "open": 47.1, "high": 48.2, "low": 46.9, "close": 47.6, "volume": 5200000}]}
```

---

## Fundamentals

### `GET /api/fundamentals/{ticker}`
25 fundamental metrics including marketCap, forwardPE, evToRevenue, revenueGrowth,
grossMargin, targetPrice, description, sector. Returns `currencySymbol` for HK/US.

---

## Clinical Trials & Pipeline

### `GET /api/trials/{ticker}`
ClinicalTrials.gov pipeline enriched with rNPV phase probabilities.
```json
{
  "trials": [
    {"nctId": "NCT04257578", "title": "BRUKINSA in Waldenström's",
     "phase": "Phase 3", "status": "RECRUITING",
     "probApproval": 0.491, "primaryCompletionDate": "2027-06"}
  ]
}
```

### `GET /api/pipeline-summary/{ticker}`
LLM (Claude) summary of the top 5 active trials.
```json
{
  "summary": "BeiGene operates a broad Phase 2/3 oncology pipeline...",
  "key_risks": ["Competitive pressure from approved BTK inhibitors", "..."],
  "upcoming_catalysts": ["BRUKINSA PCNSL readout expected Q3 2026"],
  "ai_generated": true
}
```

---

## AI Confidence Signal

### `GET /api/confidence/{ticker}`
RandomForest ML signal + LLM news sentiment + 5 weighted factor scores.
```json
{
  "score": 68, "signal": "BULLISH",
  "factors": [
    {"name": "News Sentiment", "score": 74, "weight": 0.15}
  ],
  "newsImpact": {
    "keyEvent": "FDA grants accelerated approval...",
    "sentimentScore": 0.72,
    "interpretation": "FDA approval news drove strong bullish sentiment.",
    "ai_generated": true
  }
}
```

---

## Valuation

### `GET /api/dcf/{ticker}` · `POST /api/dcf/{ticker}`
DCF intrinsic value. GET uses yfinance-derived defaults; POST accepts custom
assumptions (revenueGrowthY1–Y5, wacc, terminalGrowth, operatingMargin, taxRate).
```json
{"impliedSharePrice": 62.40, "upside": 0.31, "currencySymbol": "$", "dcf": {...}}
```

### `GET /api/scenarios/{ticker}`
3-scenario model (Bull/Base/Bear) + 1,000-path Monte Carlo with percentile bands.

---

## Cross-Border & HK-Specific

### `GET /api/dual-listing/{ticker}`
Real-time HK/US premium-discount for dual-listed GBA biotechs.
```json
{
  "dual_listed": true,
  "hk_ticker": "9688.HK", "us_ticker": "ZLAB",
  "hk_price_hkd": 14.32, "us_price_usd": 18.69,
  "us_price_hkd": 14.64, "premium_discount_pct": -2.19,
  "ads_ratio": 10.0, "usdhkd_rate": 7.782
}
```

### `GET /api/filings/{ticker}`
HKEXnews announcements (HK tickers) or news proxy (US tickers).
```json
[{"date": "2026-05-20", "title": "Monthly Return of Equity Issuer...", "type": "Monthly Return", "url": "https://..."}]
```

### `GET /api/flow/{ticker}`
12-month CCASS shareholding snapshots (HK tickers).
```json
[{"participant_id": "C00027", "participant_name": "CITIBANK N.A.",
  "shares": 5000000, "percentage": 0.25, "snapshot_date": "2026-04-30"}]
```

---

## Utility

### `GET /api/news/{ticker}`
30 recent headlines with publisher, publishedAt, url, summary.

### `GET /api/search?q={query}`
Ticker search returning symbol, shortname, exchange, quoteType.

### `GET /api/watchlist` · `POST /api/watchlist` · `DELETE /api/watchlist/{ticker}`
Persistent server-side watchlist (array of ticker strings).
