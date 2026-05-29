"""
llm_analysis.py — LLM-powered analysis for BioTerminal Pro.

Provider priority: Anthropic Claude (if ANTHROPIC_API_KEY set) → Google Gemini
(if GEMINI_API_KEY set) → graceful default.

Functions:
    analyze_news_sentiment(headlines, ticker) → sentiment dict
    summarize_pipeline(trials_df, company_name) → pipeline risk dict
    research_full_pipeline(ticker, company_name) → full pipeline research dict
"""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any

import pandas as pd
import requests as _requests

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _has_groq_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _has_openrouter_key() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def _has_any_llm() -> bool:
    return _has_api_key() or _has_groq_key() or _has_gemini_key() or _has_openrouter_key()


def _safe_err(exc: Exception) -> str:
    """Return exception message with any ?key=... query params stripped."""
    return re.sub(r"\?key=[^&\s\"']+", "?key=REDACTED", str(exc))


def _groq_generate(system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    """Call Groq (Llama 3.3 70B) via OpenAI-compatible REST — no extra package."""
    headers = {
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = _requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload, headers=headers, timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _gemini_generate(system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    """Call Gemini via REST using GEMINI_MODEL (default: gemini-1.5-flash)."""
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    resp = _requests.post(url, json=payload, timeout=90)
    if resp.status_code == 403:
        raise RuntimeError(
            "Gemini 403 Forbidden — the Generative Language API is not enabled for this "
            "project. Go to console.cloud.google.com → APIs & Services → Library → "
            "search 'Generative Language API' → Enable. "
            f"(model: {_GEMINI_MODEL})"
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"Gemini 404 — model '{_GEMINI_MODEL}' not found. "
            "Set GEMINI_MODEL env var to a valid model name, e.g. gemini-2.0-flash"
        )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _openrouter_generate(system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    """Call OpenRouter with Llama 3.3 70B (free tier, OpenAI-compatible)."""
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bioterminal.pro",
        "X-Title": "BioTerminal Pro",
    }
    payload = {
        "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = _requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload, headers=headers, timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _llm_call(system_prompt: str, user_prompt: str, max_tokens: int = 512,
              prefer_sonnet: bool = False) -> str:
    """Route to Anthropic → Groq → OpenRouter → Gemini, whichever key is set."""
    if _has_api_key():
        model = "claude-sonnet-4-6" if prefer_sonnet else _MODEL
        resp = _anthropic_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text
    if _has_groq_key():
        return _groq_generate(system_prompt, user_prompt, max_tokens)
    if _has_openrouter_key():
        return _openrouter_generate(system_prompt, user_prompt, max_tokens)
    return _gemini_generate(system_prompt, user_prompt, max_tokens)


# ---------------------------------------------------------------------------
# JSON parsing helper (handles markdown fences from the model)
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object from model output.

    Handles: markdown fences, preamble text, and large nested objects that
    non-greedy regex would truncate.
    """
    text = text.strip()
    # Strip markdown fence if present (greedy interior so nested braces are kept)
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    # Find the start of the JSON object (skip any preamble text)
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")
    # Walk to the matching closing brace to handle nested objects correctly
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    # Fall back: try to parse whatever we have
    return json.loads(text[start:])


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
    if not _has_any_llm():
        return _SENTIMENT_DEFAULT.copy()

    if not headlines:
        return {**_SENTIMENT_DEFAULT, "interpretation": "No recent headlines found."}

    headline_block = "\n".join(f"- {h}" for h in headlines[:20])
    user_prompt = f"Ticker: {ticker}\n\nRecent headlines:\n{headline_block}"

    try:
        raw = _llm_call(_SENTIMENT_SYSTEM, user_prompt, max_tokens=_MAX_TOKENS)
        result = _parse_json(raw)
        return {
            "sentiment":      result.get("sentiment", "NEUTRAL"),
            "score":          float(result.get("score", 0.0)),
            "interpretation": result.get("interpretation", ""),
            "key_events":     result.get("key_events", []),
            "ai_generated":   True,
        }
    except Exception as exc:
        logger.error("analyze_news_sentiment(%s): %s", ticker, _safe_err(exc))
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
    if not _has_any_llm():
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
        raw = _llm_call(_PIPELINE_SYSTEM, user_prompt, max_tokens=_MAX_TOKENS)
        result = _parse_json(raw)
        return {
            "summary":              result.get("summary", ""),
            "key_risks":            result.get("key_risks", []),
            "upcoming_catalysts":   result.get("upcoming_catalysts", []),
            "ai_generated":         True,
        }
    except Exception as exc:
        logger.error("summarize_pipeline(%s): %s", company_name, _safe_err(exc))
        return _PIPELINE_DEFAULT.copy()


# ---------------------------------------------------------------------------
# research_full_pipeline  — comprehensive AI pipeline research with TAM
# ---------------------------------------------------------------------------

_RESEARCH_DEFAULT: dict[str, Any] = {
    "programs":        [],
    "pipeline_summary": "AI pipeline research unavailable — set ANTHROPIC_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY.",
    "hk_china_angle":  "",
    "data_note":       "",
    "ai_generated":    False,
}


def research_full_pipeline(ticker: str, company_name: str) -> dict[str, Any]:
    """
    Comprehensive drug pipeline research. Uses Claude Sonnet if available, falls back
    to Gemini 2.0 Flash (free tier). Returns ALL programs — owned, in-licensed, partnered.
    """
    if not _has_any_llm():
        return _RESEARCH_DEFAULT.copy()

    user_prompt = (
        f"Company: {company_name}\n"
        f"Stock ticker: {ticker}\n\n"
        f"Please research and return this company's complete drug pipeline including "
        f"all clinical and significant preclinical programs, regardless of whether the "
        f"trial is registered under their name or a partner's name on ClinicalTrials.gov."
    )

    try:
        raw = _llm_call(_PIPELINE_RESEARCH_SYSTEM, user_prompt,
                        max_tokens=2048, prefer_sonnet=True)
        result = _parse_json(raw)
        return {
            "programs":         result.get("programs", []),
            "pipeline_summary": result.get("pipeline_summary", ""),
            "hk_china_angle":   result.get("hk_china_angle", ""),
            "data_note":        result.get("data_note", ""),
            "ai_generated":     True,
        }
    except Exception as exc:
        safe = _safe_err(exc)
        logger.error("research_full_pipeline(%s): %s", ticker, safe)
        result = _RESEARCH_DEFAULT.copy()
        result["pipeline_summary"] = f"AI research failed: {safe}"
        return result
