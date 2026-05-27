# Submission Checklist

**Earliest eligible submission date: 2026-08-28** (3 months after 2026-05-28 deployment)

---

## Before 2026-08-28 — collect evidence

- [ ] Export `usage_log.jsonl` stats:
      ```bash
      # Total requests
      wc -l usage_log.jsonl
      # HK vs US breakdown
      grep '"region": "HK"' usage_log.jsonl | wc -l
      grep '"region": "US"' usage_log.jsonl | wc -l
      # Unique tickers
      python3 -c "import json; tickers={json.loads(l)['ticker'] for l in open('usage_log.jsonl')}; print(len(tickers))"
      ```
- [ ] Fill usage stats into `SUBMISSION/01_narrative.md` section 3a (replace [X] placeholders)
- [ ] Add `ANTHROPIC_API_KEY` to Railway env vars to activate LLM features for demo

## Screenshots to capture (save to `SUBMISSION/screenshots/`)

- [ ] `01_homepage.png` — landing page with the terminal UI
- [ ] `02_beigene_price.png` — 6160.HK live price panel
- [ ] `03_beigene_trials.png` — clinical trial pipeline table
- [ ] `04_llm_sentiment.png` — confidence score with LLM interpretation visible
- [ ] `05_pipeline_summary.png` — LLM pipeline risk summary
- [ ] `06_ccass_flow.png` — CCASS shareholding table
- [ ] `07_dual_listing.png` — cross-border premium/discount panel
- [ ] `08_deployment_date.png` — DEPLOYMENT.md open in browser (Rule 4 evidence)
- [ ] `09_tests_passing.png` — `pytest` output showing 64 passed
- [ ] `10_pip_audit_clean.png` — `pip-audit` output showing "No known vulnerabilities"

## Demo video

- [ ] Record following `SUBMISSION/03_demo_script.md`
- [ ] Duration: 2:45–3:00
- [ ] Export as `SUBMISSION/demo_video.mp4`
- [ ] Upload to YouTube as Unlisted and paste URL into the submission form

## Submission form fields (HKICTA 2026)

- [ ] Project name: **BioTerminal Pro**
- [ ] Category: **Emerging FinTech (Non-Web3)**
- [ ] Applicant: Kyle Hui (HK resident — individual category)
- [ ] Live URL: https://web-production-cc55d.up.railway.app
- [ ] Source code: https://github.com/krentist/bioterminal-pro-2
- [ ] Deployment date: 2026-05-28 (attach `DEPLOYMENT.md` as evidence)
- [ ] Narrative: attach `SUBMISSION/01_narrative.md`
- [ ] AI governance: attach `AI_GOVERNANCE.md`
- [ ] Demo video: YouTube unlisted link

## "Best Use of AI" bonus

Check the "Best Use of AI" box on the submission form. Supporting evidence:
- LLM integration documented in `AI_GOVERNANCE.md`
- `"ai_generated": true` label in all API responses containing LLM output
- Prompt caching with `cache_control: ephemeral` documented
- RandomForest feature importances exposed (explainability)
- Rate limiting prevents LLM endpoint abuse
