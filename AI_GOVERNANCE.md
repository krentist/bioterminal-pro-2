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

## MNPI compliance wall (private research notes)

BioTerminal lets a user capture private research notes (e.g. context from management or
investor meetings) alongside public data. This capability is governed by a hard wall
(`compliance.py`, Phase J) designed to keep the user on the right side of securities law by
construction, not by discretion.

**The rule enforced.** Material non-public information (MNPI) about a *public* company — or a
tradable peer — may not be used to generate a trade-oriented signal. Trading on MNPI is
insider trading (and, under *SEC v. Panuwat*, 2021, so is "shadow trading" a related public
name).

**How it is enforced:**

- **Provenance-first capture.** Every note (`POST /api/notes`) records its source, subject,
  and a user classification: is the subject (or a tradable peer) publicly listed, and is the
  information material and non-public?
- **Automatic triage → restriction.** If a note is flagged public-subject *and*
  material-non-public, the ticker is added to a **restricted list** and an immutable
  **audit-log** entry is written (`GET /api/restricted`, `GET /api/compliance/audit`).
- **Signal suppression.** Every trade-oriented route (`/api/confidence`, `/api/dcf`,
  `/api/rnpv`, `/api/scenarios`, `/api/backtest`, and screener inclusion in `/api/screen`)
  returns a suppressed, clearly-labelled `restricted` payload for a restricted ticker and
  computes no signal for it.
- **Text never enters a signal or an LLM.** Note free-text is never fed into any computed
  signal and is never transmitted to any external service (including the Anthropic API).
  Listings are provenance-only and omit the text; retrieving a note's text is a separate,
  explicit call available only to its author.
- **Private companies are exempt.** A private company has no tradable security to abuse, so
  material information about it legitimately informs that company's own valuation.
- **Storage is local.** Notes, the restricted list, and the audit log live in a local SQLite
  database (`compliance.db`) that is git-ignored and never deployed with the app.

Acceptance is enforced by `tests/test_compliance.py`.

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
