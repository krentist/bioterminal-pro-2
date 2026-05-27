# Demo Video Script — BioTerminal Pro (3 minutes)

**Story:** A Hong Kong retail investor wants to research BeiGene (6160.HK) before
earnings. They use BioTerminal Pro to get in 3 minutes what a Bloomberg analyst
gets in 30.

---

## [0:00–0:20] Hook — Open on the live app

> *Open browser to https://web-production-cc55d.up.railway.app*

**Narration:**
"This is BioTerminal Pro — a Bloomberg Terminal-style biotech research platform
built for Hong Kong investors. I'm going to show you a full analysis of BeiGene,
one of the largest HK-listed biotechs, in under three minutes."

---

## [0:20–0:50] Price & Fundamentals

> *Type "6160.HK" in the search bar. Show the price panel loading.*

**Narration:**
"BeiGene trades on both HKEX and NASDAQ. The platform immediately pulls live
pricing, market cap, P/S ratio, and a full year of OHLCV history. Everything
routes through the HK exchange adapter — it handles the four-digit code
normalisation and HKD currency display automatically."

> *Click through to the Fundamentals tab. Point out key metrics.*

---

## [1:00–1:30] Clinical Pipeline + LLM Summary

> *Navigate to the Trials or Pipeline section.*

**Narration:**
"Here's where BioTerminal Pro is different. It queries ClinicalTrials.gov by
company name — no manual search needed — and returns BeiGene's entire registered
trial pipeline: BRUKINSA in multiple myeloma, tislelizumab across solid tumours,
and more."

> *Show the pipeline-summary endpoint output or the LLM box.*

**Narration:**
"We then send the top five active trials to Claude AI, which produces a plain-English
pipeline risk summary — key risks, upcoming catalysts, and phase distribution — all
labelled AI-generated so users know exactly what they're reading."

---

## [1:30–2:00] LLM News Sentiment + ML Confidence Signal

> *Navigate to the Confidence or Signal section.*

**Narration:**
"The confidence score combines five factors: financial health, growth momentum,
valuation, technical signals, and news sentiment. The news sentiment is no longer
keyword-matching — it's a live Claude API call on the 15 most recent headlines,
returning a score from -1 (very bearish) to +1 (very bullish), with a plain-English
interpretation right here."

> *Point to the newsImpact block in the response or the UI card.*

---

## [2:00–2:30] CCASS Flow + Dual-Listing Premium

> *Navigate to the Flow or Institutional section.*

**Narration:**
"CCASS — Hong Kong's central settlement system — publishes monthly shareholding
data. BioTerminal Pro fetches 12 months of snapshots automatically, showing how
institutional ownership has shifted over time. This data was previously only
accessible via manual HKEX website searches."

> *Then show the dual-listing panel.*

**Narration:**
"And here's something unique to BioTerminal Pro: real-time cross-border
premium-discount tracking. BeiGene's HK shares versus its NASDAQ ADS, adjusted
for the correct conversion ratio — updated live. This arbitrage signal matters to
any investor holding positions on both exchanges."

---

## [2:30–3:00] Quality & Close

> *Show the /api/docs page briefly, then the test output or GitHub.*

**Narration:**
"Under the hood: API key authentication, rate limiting, 64 automated tests all
passing, zero known CVEs, and a full AI governance document covering what data goes
to the LLM and how outputs are labelled. BioTerminal Pro has been publicly live
since May 2026 — giving HK retail investors Bloomberg-grade biotech research, free."

> *End on the live app homepage.*

---

## Recording Checklist
- [ ] Screen resolution 1920×1080 or higher
- [ ] Browser zoom at 100% (or 90% if content overflows)
- [ ] Microphone tested before recording
- [ ] Disable notifications and system popups
- [ ] Use a real network connection (not VPN) so yfinance data loads live
- [ ] Record at 30fps minimum; export as MP4 H.264
- [ ] Target duration: 2:45–3:00 (not over 3:00)
- [ ] Add captions if possible (accessibility)
