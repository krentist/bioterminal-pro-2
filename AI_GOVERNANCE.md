# AI Governance — BioTerminal Pro

This document describes how artificial intelligence is used, governed, and made
explainable within BioTerminal Pro, in accordance with HKICTA "Best Use of AI"
evaluation criteria.

---

## What AI is used for

| Feature | Location | Model | Purpose |
|---|---|---|---|
| News sentiment analysis | `llm_analysis.py` → `/api/confidence/{ticker}` | Claude Haiku 4.5 | Classify recent headlines as BULLISH / BEARISH / NEUTRAL with a confidence score |
| Pipeline risk summarisation | `llm_analysis.py` → `/api/pipeline-summary/{ticker}` | Claude Haiku 4.5 | Summarise active clinical trials, identify key risks and upcoming catalysts |
| ML confidence signal | `model.py` → `/api/confidence/{ticker}` | RandomForest | Price-based bull/bear probability from technical + fundamental features |

---

## Data sent to the LLM

**News sentiment:** Only news headline text (title strings) and the ticker symbol.
No user data, no PII, no full article content, no trading positions.

**Pipeline summary:** Clinical trial titles, phases, statuses, and primary completion
dates from ClinicalTrials.gov. Only publicly available regulatory data.
No user data, no PII.

Data is sent to the Anthropic API over TLS. Anthropic's data processing terms apply.
No data is retained by Anthropic beyond the request lifetime under their standard API policy.

---

## Transparency and labelling

All API responses that contain LLM-generated content include `"ai_generated": true`:

```json
{
  "newsImpact": {
    "sentimentScore": 0.72,
    "interpretation": "FDA approval news drove strong bullish sentiment...",
    "ai_generated": true
  }
}
```

```json
{
  "summary": "BeiGene's pipeline spans Phase 1–3 across oncology...",
  "key_risks": ["Phase 3 trial competing with approved standard of care", "..."],
  "upcoming_catalysts": ["BRUKINSA PCNSL readout Q3 2026", "..."],
  "ai_generated": true
}
```

The frontend can use this flag to label AI-generated content visually.

---

## Explainability

**RandomForest signal:** The `/api/confidence/{ticker}` response includes a `factors`
array exposing the five weighted sub-scores (Financial Health, Growth Momentum,
Valuation, Technical, News Sentiment) so users can see why the model reached its
signal. Feature importances are derived from the ticker's own price and fundamental
history — no cross-user data is used.

**LLM sentiment:** The `interpretation` field in `newsImpact` provides a plain-English
rationale alongside the numeric score, so users are not presented with a black-box number.

---

## Privacy

- No user accounts, no login, no tracking of individual users.
- The usage analytics log (`usage_log.jsonl`) records only `{date, ticker, region}` —
  no IP addresses, no user identifiers.
- LLM inputs contain only public market data (headlines, trial titles).

---

## Rate limiting and abuse prevention

- All `/api/*` routes are rate-limited to 60 requests per minute per IP via `slowapi`.
- The LLM is called at most once per `/api/confidence` request; results are not
  independently cached today but could be added with a TTL cache in a future release.
- `API_KEY` header authentication (in production) prevents unauthorised bulk use of
  the LLM-backed endpoints.

---

## Model governance

| Control | Implementation |
|---|---|
| Model version pinned | `claude-haiku-4-5-20251001` hardcoded in `llm_analysis.py` |
| Prompt caching | `cache_control: ephemeral` on system prompts — reduces cost and latency |
| Graceful degradation | Both LLM functions return `ai_generated: false` defaults if the API key is absent or the call fails — the product continues to work |
| No cross-user leakage | RandomForest is retrained per-request on the ticker's own history; no shared model state across users |
