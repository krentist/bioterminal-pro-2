"""
llm_analysis.py — Claude-powered analysis for BioTerminal Pro.

Functions:
    analyze_news_sentiment(headlines, ticker) → sentiment dict
    summarize_pipeline(trials_df, company_name) → pipeline risk dict

Both functions:
  - Use prompt caching (cache_control: ephemeral on system prompts) to minimise cost.
  - Return a graceful default if ANTHROPIC_API_KEY is absent or the call fails.
  - Label outputs with ai_generated=True so callers can surface that to users.
"""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512


# ---------------------------------------------------------------------------
# Client (lazy, cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------------------------
# JSON parsing helper (handles markdown fences from the model)
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Cacheable system prompts
# ---------------------------------------------------------------------------

_SENTIMENT_SYSTEM = """\
You are a senior biotech investment analyst specialising in FDA catalysts, clinical \
trial readouts, and pharmaceutical M&A. You will receive a list of recent news \
headlines for a publicly listed biotech company and return a structured JSON \
assessment of market sentiment.

Return exactly this JSON object — no markdown fences, no extra text:
{
  "sentiment": "<BULLISH|BEARISH|NEUTRAL>",
  "score": <float from -1.0 (very bearish) to +1.0 (very bullish)>,
  "interpretation": "<1-2 sentence plain-English rationale>",
  "key_events": ["<most market-moving headline>", "<second most important>"]
}

Rules:
- Weigh FDA approvals, clinical successes, and M&A heavily bullish.
- Weigh trial failures, FDA rejections, and safety signals heavily bearish.
- key_events: up to 3 entries, exact headline text where possible.
- If no headlines are provided, return NEUTRAL with score 0.0.\
"""

_PIPELINE_SYSTEM = """\
You are a biotech clinical development expert and portfolio strategist. You will \
receive a list of active clinical trials for a company and return a structured JSON \
risk and catalyst summary.

Return exactly this JSON object — no markdown fences, no extra text:
{
  "summary": "<2-3 sentence overview: phase distribution, therapeutic areas, pipeline strength>",
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "upcoming_catalysts": ["<catalyst 1>", "<catalyst 2>"]
}

Rules:
- key_risks: clinical, regulatory, or competitive risks specific to this pipeline.
- upcoming_catalysts: highlight trials with near-term completion dates or pivotal readouts.
- Be concise — each list entry should be one sentence.\
"""

_PIPELINE_RESEARCH_SYSTEM = """\
You are a senior biotech equity analyst at a tier-1 investment bank covering Hong Kong \
and US-listed biopharmaceuticals. You have deep familiarity with drug pipelines sourced \
from annual reports, investor presentations, HKEX/SEC filings, ClinicalTrials.gov, \
ChiCTR (China Clinical Trial Registry), and press releases.

Given a company name and ticker, return a comprehensive pipeline analysis covering ALL \
known programs — owned, in-licensed, and partnered — including preclinical assets if \
publicly disclosed.

Critical nuance for HK-listed biotechs: many trials are registered under a PARTNER \
company's name on ClinicalTrials.gov (e.g. Inhibrx, Lilly, AstraZeneca), not the \
HK company. Include these and note the trial sponsor/partner.

Return EXACTLY this JSON structure — no markdown fences, no extra text:
{
  "programs": [
    {
      "drug_name": "Generic or code name (e.g. Osemitamab / TST001)",
      "target": "Molecular target (e.g. CLDN18.2)",
      "mechanism": "One-line MOA (e.g. Anti-CLDN18.2 IgG1 monoclonal antibody)",
      "indication": "Primary indication (e.g. Gastric/GEJ cancer)",
      "secondary_indications": [],
      "phase": "Preclinical|Phase 1|Phase 1/2|Phase 2|Phase 2/3|Phase 3|Approved|Discontinued",
      "status": "Active|Recruiting|Completed|Suspended|Discontinued|Not yet recruiting",
      "owned_or_licensed": "Owned|In-licensed|Out-licensed",
      "partner": "Partner company name or null",
      "rights": "Geographic rights this company holds (e.g. Greater China, Global, Asia-Pacific)",
      "nct_ids": ["NCT05190575"],
      "chictr_ids": [],
      "tam_usd_bn": 4.5,
      "tam_basis": "~130k annual gastric cancer incidence in China + Japan; $35k/yr treatment × 40% penetration ≈ $1.8B China TAM; global TAM ~$4.5B by 2030",
      "competition": ["Zolbetuximab (Astellas)", "other competitor drugs"],
      "key_data": ["Phase 1/2a ORR 35% in 1L G/GEJ (n=20, ASCO 2024)"],
      "risk": "LOW|MEDIUM|HIGH|VERY_HIGH",
      "next_catalyst": "Phase 2 interim data expected H1 2026"
    }
  ],
  "pipeline_summary": "2-3 sentence overall pipeline assessment covering stage distribution, therapeutic focus, and differentiation",
  "hk_china_angle": "Specific Greater Bay Area / China market opportunity or NMPA regulatory pathway notes",
  "data_note": "Brief note on data vintage and what may have changed since training cutoff"
}

Formatting rules:
- tam_usd_bn: null if genuinely unknown; never fabricate a number. Show your logic in tam_basis.
- nct_ids / chictr_ids: include only if you know them with high confidence; empty array otherwise.
- competition: top 2-3 drugs in same indication/target class, not an exhaustive list.
- Do NOT omit programs just because trials are registered under a partner's name.
- risk: base on phase, data quality, competition density, and binary event risk.\
"""


# ---------------------------------------------------------------------------
# analyze_news_sentiment
# ---------------------------------------------------------------------------

_SENTIMENT_DEFAULT = {
    "sentiment": "NEUTRAL",
    "score": 0.0,
    "interpretation": "Insufficient data for LLM sentiment analysis.",
    "key_events": [],
    "ai_generated": False,
}


def analyze_news_sentiment(headlines: list[str], ticker: str) -> dict:
    """
    Analyse a list of news headlines with Claude and return a sentiment dict.

    Returns a default NEUTRAL dict if the API key is missing or the call fails.
    All successful responses include ai_generated=True.
    """
    if not _has_api_key():
        return _SENTIMENT_DEFAULT.copy()

    if not headlines:
        return {**_SENTIMENT_DEFAULT, "interpretation": "No recent headlines found."}

    headline_block = "\n".join(f"- {h}" for h in headlines[:20])
    user_prompt = f"Ticker: {ticker}\n\nRecent headlines:\n{headline_block}"

    try:
        resp = _client().messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _SENTIMENT_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text
        result = _parse_json(raw)
        return {
            "sentiment":      result.get("sentiment", "NEUTRAL"),
            "score":          float(result.get("score", 0.0)),
            "interpretation": result.get("interpretation", ""),
            "key_events":     result.get("key_events", []),
            "ai_generated":   True,
        }
    except Exception as exc:
        logger.error("analyze_news_sentiment(%s): %s", ticker, exc)
        return _SENTIMENT_DEFAULT.copy()


# ---------------------------------------------------------------------------
# summarize_pipeline
# ---------------------------------------------------------------------------

_PIPELINE_DEFAULT = {
    "summary": "Insufficient trial data for LLM pipeline summary.",
    "key_risks": [],
    "upcoming_catalysts": [],
    "ai_generated": False,
}


def summarize_pipeline(trials_df: pd.DataFrame, company_name: str) -> dict:
    """
    Summarise a company's clinical trial pipeline with Claude.

    Passes the top 5 active trials (title, phase, status, primary completion date).
    Returns a default dict if the API key is missing or the call fails.
    """
    if not _has_api_key():
        return _PIPELINE_DEFAULT.copy()

    if trials_df is None or trials_df.empty:
        return {**_PIPELINE_DEFAULT, "summary": "No active trials found in the pipeline."}

    active = trials_df[
        trials_df.get("status", pd.Series(dtype=str)).str.upper().isin(
            {"RECRUITING", "ACTIVE, NOT RECRUITING", "ENROLLING BY INVITATION", "NOT YET RECRUITING"}
        )
    ] if "status" in trials_df.columns else trials_df

    top5 = (active if not active.empty else trials_df).head(5)

    trial_lines = []
    for _, row in top5.iterrows():
        trial_lines.append(
            f"- {row.get('title', 'Untitled')} | Phase: {row.get('phase', 'N/A')} "
            f"| Status: {row.get('status', 'N/A')} "
            f"| Completion: {row.get('primary_completion_date', 'N/A')}"
        )

    user_prompt = (
        f"Company: {company_name}\n\n"
        f"Active clinical trials:\n" + "\n".join(trial_lines)
    )

    try:
        resp = _client().messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _PIPELINE_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text
        result = _parse_json(raw)
        return {
            "summary":              result.get("summary", ""),
            "key_risks":            result.get("key_risks", []),
            "upcoming_catalysts":   result.get("upcoming_catalysts", []),
            "ai_generated":         True,
        }
    except Exception as exc:
        logger.error("summarize_pipeline(%s): %s", company_name, exc)
        return _PIPELINE_DEFAULT.copy()


# ---------------------------------------------------------------------------
# research_full_pipeline  — comprehensive AI pipeline research with TAM
# ---------------------------------------------------------------------------

_RESEARCH_DEFAULT: dict[str, Any] = {
    "programs":        [],
    "pipeline_summary": "AI pipeline research unavailable — ANTHROPIC_API_KEY not set.",
    "hk_china_angle":  "",
    "data_note":       "",
    "ai_generated":    False,
}

_RESEARCH_MODEL = "claude-sonnet-4-6"  # use Sonnet for richer knowledge


def research_full_pipeline(ticker: str, company_name: str) -> dict[str, Any]:
    """
    Comprehensive drug pipeline research using Claude.

    Returns ALL known programs — owned, in-licensed, partnered — with TAM estimates
    and competitive context. Uses Sonnet (better knowledge) rather than Haiku.
    Falls back gracefully if the API key is absent.
    """
    if not _has_api_key():
        return _RESEARCH_DEFAULT.copy()

    user_prompt = (
        f"Company: {company_name}\n"
        f"Stock ticker: {ticker}\n\n"
        f"Please research and return this company's complete drug pipeline including "
        f"all clinical and significant preclinical programs, regardless of whether the "
        f"trial is registered under their name or a partner's name on ClinicalTrials.gov."
    )

    try:
        resp = _client().messages.create(
            model=_RESEARCH_MODEL,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": _PIPELINE_RESEARCH_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = resp.content[0].text
        result = _parse_json(raw)
        return {
            "programs":        result.get("programs", []),
            "pipeline_summary": result.get("pipeline_summary", ""),
            "hk_china_angle":  result.get("hk_china_angle", ""),
            "data_note":       result.get("data_note", ""),
            "ai_generated":    True,
        }
    except Exception as exc:
        logger.error("research_full_pipeline(%s): %s", ticker, exc)
        return _RESEARCH_DEFAULT.copy()
