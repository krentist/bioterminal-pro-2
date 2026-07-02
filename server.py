"""
server.py — BioTerminal Pro FastAPI backend.

Serves:
  /api/*     → Python data routes (yfinance, ClinicalTrials.gov, ML model)
  /          → React SPA (index.html + /assets/*)

Run:
  uvicorn server:app --reload --port 8000
  then open http://localhost:8000
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import re
from urllib.parse import quote as _url_quote

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import data_fetcher as df_mod
from data_fetcher import fetch_clinicaltrials, fetch_clinicaltrials_by_nct_ids, fetch_yfinance_news
import alpha_screener as _screener
import backtester as _backtester
import devils_advocate as _devil
import earnings_analyzer as _earnings
from dual_listing import get_dual_listing_info
from exchanges import get_exchange_adapter
from llm_analysis import analyze_news_sentiment, summarize_pipeline, research_full_pipeline
from model import predict as ml_predict
from pipeline_analyzer import enrich_trials
from rnpv_calculator import pipeline_rnpv, DEFAULT_PEAK_SALES_USD
from utils import period_to_dates

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="BioTerminal Pro", docs_url="/api/docs")
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Ticker validation
# ---------------------------------------------------------------------------

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
# Matches /api/<endpoint>/<ticker> (with optional /port/5000 prefix)
_TICKER_PATH_RE = re.compile(r"^(?:/port/5000)?/api/[^/]+/([^/?]+)")

_PUBLIC_API_PATHS = {"/api/docs", "/api/openapi.json", "/api/redoc"}


class _ValidateTickerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        m = _TICKER_PATH_RE.match(request.url.path)
        if m and not request.url.path.rstrip("/").endswith(("/api/docs", "/api/redoc")):
            if not _TICKER_RE.match(m.group(1).upper()):
                return JSONResponse(status_code=400, content={"detail": "Invalid ticker symbol"})
        return await call_next(request)


# ---------------------------------------------------------------------------
# API key authentication (skipped in development mode)
# ---------------------------------------------------------------------------

class _APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.getenv("ENV", "production") != "production":  # safe default: production
            return await call_next(request)
        raw_path = request.url.path
        # Requests via /port/5000/ are from the compiled SPA — allow without key.
        if raw_path.startswith("/port/5000/"):
            return await call_next(request)
        # Same-origin browser requests (SPA fetch) carry a Referer matching this host.
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        if host and referer and (
            referer.startswith(f"https://{host}/") or referer.startswith(f"http://{host}/")
        ):
            return await call_next(request)
        path = raw_path
        if path.startswith("/api/") and path not in _PUBLIC_API_PATHS:
            api_key = os.getenv("API_KEY", "")
            if api_key and request.headers.get("X-API-Key") != api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: missing or invalid API key"},
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Middleware stack
# Starlette wraps in reverse order: first added = innermost (runs last).
# Request flow: CORS → SlowAPI → APIKey → ValidateTicker → StripPrefix → Router
# ---------------------------------------------------------------------------

# Perplexity hardcodes /port/5000 as the API prefix in the compiled JS.
# Strip it before routing so all /api/* handlers work unchanged.
class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "rid=%s method=%s path=%s status=%d duration_ms=%d",
            request_id, request.method, request.url.path,
            response.status_code, duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response


class _StripPerplexityPrefix(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/port/5000"):
            request.scope["path"] = request.url.path[len("/port/5000"):]
        return await call_next(request)


_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]

app.add_middleware(_StripPerplexityPrefix)       # innermost
app.add_middleware(_RequestLoggingMiddleware)
app.add_middleware(_ValidateTickerMiddleware)
app.add_middleware(_APIKeyMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(                              # outermost — handles CORS preflight first
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

BASE_DIR = Path(__file__).parent

# Persistent watchlist (simple JSON file)
WATCHLIST_PATH = BASE_DIR / "watchlist.json"

# Append-only usage analytics log (no PII — ticker + region + date only)
USAGE_LOG_PATH = BASE_DIR / "usage_log.jsonl"
_usage_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _currency_symbol(currency: str) -> str:
    return {"USD": "$", "HKD": "HK$", "CNY": "¥", "EUR": "€", "GBP": "£"}.get(currency, "$")


def _load_watchlist() -> list[str]:
    try:
        return json.loads(WATCHLIST_PATH.read_text())
    except Exception:
        return ["MRNA", "REGN", "VRTX", "AMGN", "GILD"]


def _save_watchlist(tickers: list[str]) -> None:
    WATCHLIST_PATH.write_text(json.dumps(list(dict.fromkeys(tickers))))


def _safe(v, fallback=None):
    if v is None:
        return fallback
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return fallback
    return v


def _log_usage(ticker: str) -> None:
    """Append one usage record to usage_log.jsonl (thread-safe, best-effort)."""
    try:
        region = "HK" if ticker.upper().endswith(".HK") else "US"
        entry  = json.dumps({"date": datetime.utcnow().strftime("%Y-%m-%d"), "ticker": ticker.upper(), "region": region})
        with _usage_lock:
            with open(USAGE_LOG_PATH, "a") as f:
                f.write(entry + "\n")
    except Exception:
        pass


def _to_json_safe(obj):
    """Recursively replace NaN/Inf with None for JSON serialisation (dicts and lists)."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if (math.isnan(obj) or math.isinf(obj)) else float(obj)
    return obj


# ============================================================
# /api/quote/{ticker}  — current price + daily change
# ============================================================

@app.get("/api/quote/{ticker}")
def get_quote(ticker: str):
    _log_usage(ticker)
    try:
        info = df_mod._cached_yf_info(ticker)
        price        = _safe(info.get("regularMarketPrice") or info.get("currentPrice"))
        prev_close   = _safe(info.get("regularMarketPreviousClose") or info.get("previousClose"))
        change_pct   = ((price / prev_close) - 1) if price and prev_close else None
        currency     = info.get("currency", "USD")
        if not price:
            hist = df_mod.get_price_history(ticker, period="5d")
            if not hist.empty:
                price      = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
                change_pct = (price / prev_close - 1) if prev_close else None
        return {
            "price":          _safe(price),
            "changePercent":  _safe(change_pct),
            "currency":       currency,
            "currencySymbol": _currency_symbol(currency),
        }
    except Exception as exc:
        logger.error("quote(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/realtime/{ticker}  — same as quote, polled every 30s
# ============================================================

@app.get("/api/realtime/{ticker}")
def get_realtime(ticker: str):
    return get_quote(ticker)


# ============================================================
# /api/stock/{ticker}?range=1y  — OHLCV bars
# ============================================================

@app.get("/api/stock/{ticker}")
def get_stock(ticker: str, range: str = "1y"):
    # Normalise both the UI range labels (1D, 1W, 1M, 3M, 1Y, 5Y) and raw
    # yfinance period strings (1d, 5d, 1mo, ...) to a canonical period key.
    _RANGE_ALIASES = {
        "1D": "1d", "1W": "5d", "1M": "1mo", "3M": "3mo",
        "6M": "6mo", "1Y": "1y", "2Y": "2y", "5Y": "5y", "MAX": "max",
    }
    period_key = _RANGE_ALIASES.get(range.upper(), range.lower())
    _PERIOD_MAP = {
        "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo",
        "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y", "max": "max",
    }
    yf_period = _PERIOD_MAP.get(period_key, "1y")
    _INTERVAL_MAP = {
        "1d": "2m",  "5d": "15m", "1mo": "1h",  "3mo": "1d",
        "6mo": "1d", "1y": "1d",  "2y": "1d",   "5y": "1wk", "max": "1mo",
    }
    interval = _INTERVAL_MAP.get(period_key, "1d")
    try:
        hist = df_mod.get_price_history(ticker, period=yf_period, interval=interval)
        if hist.empty:
            return {"bars": []}
        bars = []
        for ts, row in hist.iterrows():
            bars.append({
                "time":   ts.strftime("%Y-%m-%dT%H:%M:%S") if interval in ("2m","15m","1h") else ts.strftime("%Y-%m-%d"),
                "open":   _safe(float(row["Open"])),
                "high":   _safe(float(row["High"])),
                "low":    _safe(float(row["Low"])),
                "close":  _safe(float(row["Close"])),
                "volume": int(row["Volume"]) if not math.isnan(row["Volume"]) else 0,
            })
        return {"bars": bars}
    except Exception as exc:
        logger.error("stock(%s): %s", ticker, exc)
        return {"bars": []}


# ============================================================
# /api/fundamentals/{ticker}
# ============================================================

@app.get("/api/fundamentals/{ticker}")
def get_fundamentals(ticker: str):
    try:
        info     = df_mod._cached_yf_info(ticker)
        currency = info.get("currency", "USD")
        return _to_json_safe({
            "marketCap":       info.get("marketCap"),
            "enterpriseValue": info.get("enterpriseValue"),
            "forwardPE":       info.get("forwardPE"),
            "trailingPE":      info.get("trailingPE"),
            "evToRevenue":     info.get("enterpriseToRevenue"),
            "evToEbitda":      info.get("enterpriseToEbitda"),
            "beta":            info.get("beta"),
            "revenue":         info.get("totalRevenue"),
            "revenueGrowth":   info.get("revenueGrowth"),
            "grossMargin":     info.get("grossMargins"),
            "operatingMargin": info.get("operatingMargins"),
            "profitMargin":    info.get("profitMargins"),
            "roe":             info.get("returnOnEquity"),
            "roa":             info.get("returnOnAssets"),
            "debtToEquity":    info.get("debtToEquity"),
            "currentRatio":    info.get("currentRatio"),
            "cash":            info.get("totalCash"),
            "totalDebt":       info.get("totalDebt"),
            "sharesOutstanding": info.get("sharesOutstanding"),
            "floatShares":     info.get("floatShares"),
            "week52High":      info.get("fiftyTwoWeekHigh"),
            "week52Low":       info.get("fiftyTwoWeekLow"),
            "averageVolume":   info.get("averageVolume"),
            "dividendYield":   info.get("dividendYield"),
            "payoutRatio":     info.get("payoutRatio"),
            "targetPrice":     info.get("targetMeanPrice"),
            "analystCount":    info.get("numberOfAnalystOpinions"),
            "recommendation":  info.get("recommendationKey"),
            "currency":        currency,
            "currencySymbol":  _currency_symbol(currency),
            # Description + identifiers for the overview tab
            "name":            info.get("longName") or info.get("shortName", ticker),
            "description":     info.get("longBusinessSummary"),
            "sector":          info.get("sector"),
            "industry":        info.get("industry"),
            "country":         info.get("country"),
            "website":         info.get("website"),
            "employees":       info.get("fullTimeEmployees"),
            "exchange":        info.get("exchange"),
        })
    except Exception as exc:
        logger.error("fundamentals(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/trials/{ticker}  — ClinicalTrials.gov
# ============================================================

@app.get("/api/trials/{ticker}")
def get_trials(ticker: str):
    try:
        raw = fetch_clinicaltrials(ticker)
        if raw.empty:
            return {"trials": []}
        enriched = enrich_trials(raw)
        trials = []
        for _, row in enriched.iterrows():
            nct_id = row.get("nct_id")
            trials.append({
                "nctId":    nct_id,
                "title":    row.get("title"),
                "phase":    row.get("phase_clean") or row.get("phase"),
                "status":   row.get("status"),
                "condition":row.get("condition"),
                "enrollment": _safe(row.get("enrollment")),
                "startDate":  row.get("start_date"),
                "primaryCompletionDate": row.get("primary_completion_date"),
                "sponsor":  row.get("sponsor"),
                "probApproval": _safe(float(row.get("prob_approval", 0))),
                "registry": "ClinicalTrials.gov",
                "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
            })
        return _to_json_safe({"trials": trials})
    except Exception as exc:
        logger.error("trials(%s): %s", ticker, exc)
        return {"trials": []}


# ============================================================
# /api/news/{ticker}
# ============================================================

@app.get("/api/news/{ticker}")
def get_news(ticker: str):
    try:
        df = fetch_yfinance_news(ticker, limit=30)
        if df.empty:
            return []
        articles = []
        for _, row in df.iterrows():
            pub = row.get("date")
            if isinstance(pub, datetime):
                pub_str = pub.isoformat()
            elif pub:
                pub_str = str(pub)
            else:
                pub_str = None
            articles.append({
                "title":       row.get("title", ""),
                "publisher":   row.get("source", ""),
                "publishedAt": pub_str,
                "url":         row.get("url", ""),
                "summary":     row.get("summary", ""),
            })
        return articles
    except Exception as exc:
        logger.error("news(%s): %s", ticker, exc)
        return []


# ============================================================
# /api/confidence/{ticker}  — ML signal
# ============================================================

_FACTOR_WEIGHTS = {
    "Financial Health": 0.25,
    "Growth Momentum":  0.20,
    "Valuation":        0.20,
    "Technical":        0.20,
    "News Sentiment":   0.15,
}


def _build_confidence_payload(ticker: str, prices: "pd.DataFrame", funds: dict, ml_result) -> dict:
    """
    Build the full confidence response the React UI component requires.

    Score = weighted sum of 5 factors (0-100). Signal derived from that score.
    ML result is included as context under mlSignal — it does not drive the score,
    which prevents the factor breakdown from being inconsistent with the headline number.
    """
    info = {}
    try:
        info = df_mod._cached_yf_info(ticker)
    except Exception:
        pass

    def _clamp(v): return max(0, min(100, int(round(v))))

    # Factor scores
    cur_ratio  = _safe(info.get("currentRatio"), 1.0)
    profit_mgn = _safe(info.get("profitMargins"), 0.0)
    d_to_e     = _safe(info.get("debtToEquity"), 50.0)
    financial_health = _clamp(50 + (cur_ratio - 1.5) * 10 + profit_mgn * 80 - max(0, d_to_e - 50) * 0.2)

    rev_growth  = _safe(info.get("revenueGrowth"), 0.0)
    earn_growth = _safe(info.get("earningsGrowth"), 0.0)
    growth_momentum = _clamp(50 + rev_growth * 120 + earn_growth * 80)

    fwd_pe    = _safe(info.get("forwardPE"), 30.0)
    ev_rev    = _safe(info.get("enterpriseToRevenue"), 5.0)
    target    = _safe(info.get("targetMeanPrice"), 0.0)
    price_now = _safe(info.get("regularMarketPrice") or info.get("currentPrice"), 0.0)
    upside    = (target / price_now - 1) if (target and price_now) else 0.0
    valuation = _clamp(50 - (fwd_pe - 20) * 0.5 - (ev_rev - 4) * 1.5 + upside * 60)

    technical = 50
    try:
        if not prices.empty and len(prices) >= 20:
            col = "Close" if "Close" in prices.columns else prices.columns[3]
            closes = prices[col].dropna().values
            if len(closes) >= 15:
                delta  = np.diff(closes[-15:])
                gains  = np.where(delta > 0, delta, 0).mean()
                losses = np.where(delta < 0, -delta, 0).mean()
                rs     = gains / losses if losses > 0 else 100.0
                rsi    = 100 - 100 / (1 + rs)
                tech   = 50 + (rsi - 50) * 0.4 + (10 if closes[-1] > closes[-20:].mean() else -10)
                technical = _clamp(tech)
    except Exception:
        pass

    # News sentiment via LLM (falls back to NEUTRAL if key absent)
    news_sentiment  = 50
    key_event       = None
    recent_count    = 0
    sentiment_score = 0.0
    llm_result: dict = {}
    try:
        news_df = fetch_yfinance_news(ticker, limit=15)
        if not news_df.empty:
            recent_count = len(news_df)
            headlines    = news_df["title"].dropna().tolist()
            llm_result   = analyze_news_sentiment(headlines, ticker)
            sentiment_score = round(llm_result.get("score", 0.0), 2)
            news_sentiment = _clamp(50 + sentiment_score * 50)
            events = llm_result.get("key_events", [])
            key_event = events[0] if events else (headlines[0] if headlines else None)
    except Exception:
        pass

    factors = [
        {"name": "Financial Health", "score": financial_health, "weight": _FACTOR_WEIGHTS["Financial Health"]},
        {"name": "Growth Momentum",  "score": growth_momentum,  "weight": _FACTOR_WEIGHTS["Growth Momentum"]},
        {"name": "Valuation",        "score": valuation,        "weight": _FACTOR_WEIGHTS["Valuation"]},
        {"name": "Technical",        "score": technical,        "weight": _FACTOR_WEIGHTS["Technical"]},
        {"name": "News Sentiment",   "score": news_sentiment,   "weight": _FACTOR_WEIGHTS["News Sentiment"]},
    ]

    # Score = weighted sum of factors; signal derived from thresholds
    weighted_score = sum(f["score"] * f["weight"] for f in factors)
    score  = _clamp(weighted_score)
    signal = "BULLISH" if score >= 60 else ("BEARISH" if score <= 40 else "NEUTRAL")

    return _to_json_safe({
        "score":      score,
        "signal":     signal,
        "factors":    factors,
        "mlSignal":   {
            "signal":      ml_result.signal,
            "bullProb":    ml_result.bull_prob,
            "confidence":  ml_result.confidence,
            "trainedOn":   ml_result.trained_on,
            "oosAccuracy": ml_result.oos_accuracy,
            "oosSamples":  ml_result.oos_samples,
        },
        "newsImpact": {
            "keyEvent":       key_event,
            "recentCount":    recent_count,
            "sentimentScore": sentiment_score,
            "interpretation": llm_result.get("interpretation"),
            "keyEvents":      llm_result.get("key_events", []),
            "ai_generated":   llm_result.get("ai_generated", False),
        },
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    })


def _default_confidence() -> dict:
    factors = [
        {"name": n, "score": 50, "weight": w}
        for n, w in _FACTOR_WEIGHTS.items()
    ]
    return {
        "score": 50, "signal": "NEUTRAL", "factors": factors,
        "newsImpact": {"keyEvent": None, "recentCount": 0, "sentimentScore": 0.0},
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/confidence/{ticker}")
def get_confidence(ticker: str):
    now = time.monotonic()
    cached, ts = _CONFIDENCE_CACHE.get(ticker.upper(), (None, 0.0))
    if cached is not None and now - ts < _CONFIDENCE_CACHE_TTL:
        return cached
    try:
        prices = df_mod.get_price_history(ticker, period="2y")
        funds  = df_mod.get_financial_metrics(ticker)
        if prices.empty or len(prices) < 120:
            return _default_confidence()

        # Fetch sector benchmark aligned to ticker's trading days.
        # US biotech → XBI (SPDR S&P Biotech ETF); HK → 2800.HK (Tracker Fund).
        # Falls back to absolute-return target if benchmark unavailable.
        sector_closes: "pd.Series | None" = None
        try:
            benchmark = "2800.HK" if ticker.upper().endswith(".HK") else "XBI"
            sec_hist  = df_mod.get_price_history(benchmark, period="2y")
            if not sec_hist.empty:
                aligned = sec_hist["Close"].reindex(prices.index, method="ffill").dropna()
                if len(aligned) >= len(prices) * 0.9:
                    sector_closes = aligned.reindex(prices.index)
        except Exception:
            pass

        result  = ml_predict(ticker, prices, sector_closes=sector_closes)
        payload = _build_confidence_payload(ticker, prices, funds, result)
        _CONFIDENCE_CACHE[ticker.upper()] = (payload, time.monotonic())
        return payload
    except Exception as exc:
        logger.error("confidence(%s): %s", ticker, exc)
        return _default_confidence()


# ============================================================
# /api/dcf/{ticker}  — DCF valuation  (GET defaults, POST custom)
# ============================================================

def _sponsor_match_terms(ticker: str, company_name: str) -> list[str]:
    """Lower-cased name fragments that identify this company as a trial's lead sponsor."""
    terms: list[str] = []
    overrides = df_mod._CT_TICKER_NAME_OVERRIDES.get(ticker.upper(), [])
    for name in overrides + df_mod._ct_name_variants(company_name or ticker):
        n = (name or "").strip().lower()
        if len(n) >= 4 and n not in terms:
            terms.append(n)
    return terms


def _select_pipeline_programs(enriched: "pd.DataFrame", ticker: str, company_name: str) -> tuple["pd.DataFrame", bool]:
    """
    Turn a raw trials DataFrame into a defensible list of *programs* for rNPV.

    1. Keep only trials this company actually leads (sponsor name matches), so
       collaborator/registry noise (NCI, cooperative groups, unrelated studies) is
       dropped. If nothing matches (common for HK biotechs whose trials are
       registered under a partner), fall back to all trials and flag it.
    2. De-duplicate to one program per (phase, primary indication), preferring
       active trials with larger enrollment — so the same drug run across several
       trials is not counted as several $500M assets.
    """
    if enriched.empty:
        return enriched, False

    terms = _sponsor_match_terms(ticker, company_name)
    sponsor_l = enriched.get("sponsor", pd.Series("", index=enriched.index)).fillna("").str.lower()
    mask = sponsor_l.apply(lambda s: any(t in s for t in terms)) if terms else pd.Series(False, index=enriched.index)
    sponsor_matched = bool(mask.any())
    df = enriched[mask].copy() if sponsor_matched else enriched.copy()

    cond = df.get("condition", pd.Series("", index=df.index)).fillna("")
    df["_indication"] = cond.str.split(",").str[0].str.strip().str.lower()
    df["_key"] = df["phase_clean"].astype(str) + "|" + df["_indication"]
    sort_cols = [c for c in ("is_active", "enrollment") if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False, na_position="last")
    df = df.drop_duplicates("_key").drop(columns=["_indication", "_key"])
    return df, sponsor_matched


def _rnpv_valuation(ticker: str, info: dict) -> dict:
    """Compute rNPV-based valuation for pre-revenue pipeline companies."""
    currency   = info.get("currency", "USD")
    shares_out = _safe(info.get("sharesOutstanding"), 1e9)
    current_px = _safe(info.get("regularMarketPrice") or info.get("currentPrice"), 0)
    mktcap     = _safe(info.get("marketCap"), 0)
    company_name = info.get("longName") or info.get("shortName") or ticker

    raw      = fetch_clinicaltrials(ticker)
    enriched = enrich_trials(raw) if not raw.empty else raw
    trials_found = int(len(enriched))
    programs, sponsor_matched = _select_pipeline_programs(enriched, ticker, company_name) if not enriched.empty else (enriched, False)
    total_rnpv, detail_df = pipeline_rnpv(programs)

    rnpv_per_share = (total_rnpv / shares_out) if shares_out else None
    upside = (rnpv_per_share / current_px - 1) if (rnpv_per_share and current_px) else None
    pipeline_discount = ((total_rnpv / mktcap) - 1) if (mktcap and mktcap > 0) else None

    detail = []
    for _, row in detail_df.iterrows():
        detail.append({
            "name":          str(row.get("name", ""))[:60],
            "phase":         row.get("phase"),
            "probApproval":  round(float(row.get("prob_approval", 0)), 4),
            "peakSales":     row.get("peak_sales"),
            "rnpv":          row.get("rnpv"),
            "devCostPv":     row.get("dev_cost_pv"),
            "netRnpv":       row.get("net_rnpv"),
        })

    return _to_json_safe({
        "impliedSharePrice": round(rnpv_per_share, 2) if rnpv_per_share else None,
        "upside":            round(upside, 4) if upside is not None else None,
        "currencySymbol":    _currency_symbol(currency),
        "valuationMethod":   "rNPV",
        "rnpvTotal":         round(total_rnpv, 0),
        "rnpvPerShare":      round(rnpv_per_share, 2) if rnpv_per_share else None,
        "pipelineDiscount":  round(pipeline_discount, 4) if pipeline_discount is not None else None,
        "rnpvDetail":        detail,
        "dcf":               None,
        # Transparency: what was actually valued and under what blanket assumption.
        "trialsFound":       trials_found,
        "programsValued":    int(len(detail_df)),
        "sponsorMatched":    sponsor_matched,
        "peakSalesAssumption": DEFAULT_PEAK_SALES_USD,
        "assumptionNote": (
            "Programs = this company's lead-sponsor trials, de-duplicated by phase and "
            "indication. Each program uses a uniform " f"${DEFAULT_PEAK_SALES_USD/1e6:.0f}M "
            "peak-sales placeholder (not drug-specific), so totals are a rough pipeline-scale "
            "estimate, not a per-asset valuation."
            if sponsor_matched else
            "No trials on ClinicalTrials.gov are registered under this company as lead sponsor "
            "(common for HK/China biotechs whose trials sit under a partner). rNPV is computed "
            "over all name-matched trials and is therefore unreliable — treat as indicative only."
        ),
    })


def _run_dcf(ticker: str, assumptions: dict) -> dict:
    """Compute DCF intrinsic value. Falls back to rNPV for pre-revenue companies."""
    try:
        info        = df_mod._cached_yf_info(ticker)
        currency    = info.get("currency", "USD")
        shares_out  = _safe(info.get("sharesOutstanding"), 1e9)
        revenue     = _safe(info.get("totalRevenue"), 0)
        current_px  = _safe(info.get("regularMarketPrice") or info.get("currentPrice"), 0)
        op_margin_actual = _safe(info.get("operatingMargins"), None)

        # DCF is only coherent for a company that already generates operating profit.
        # For pre-revenue or loss-making biotech (the bulk of this universe) a DCF built
        # on assumed positive margins prints a fictitious number, so route to rNPV.
        if not revenue or revenue <= 0:
            return _rnpv_valuation(ticker, info)
        if op_margin_actual is None or op_margin_actual <= 0:
            return _rnpv_valuation(ticker, info)

        # Clamp per-year growth so a single noisy yfinance revenueGrowth value can't
        # compound into a fantasy valuation.
        def _clamp_growth(x: float) -> float:
            return min(max(float(x), -0.5), 0.60)

        g = [
            _clamp_growth(assumptions.get("revenueGrowthY1", 0.15)),
            _clamp_growth(assumptions.get("revenueGrowthY2", 0.12)),
            _clamp_growth(assumptions.get("revenueGrowthY3", 0.10)),
            _clamp_growth(assumptions.get("revenueGrowthY4", 0.08)),
            _clamp_growth(assumptions.get("revenueGrowthY5", 0.06)),
        ]
        wacc       = assumptions.get("wacc", 0.10)
        terminal_g = assumptions.get("terminalGrowth", 0.03)
        op_margin  = assumptions.get("operatingMargin", 0.20)
        tax_rate   = assumptions.get("taxRate", 0.21)
        capex_pct  = assumptions.get("capexPercent", 0.05)

        if shares_out <= 0:
            return _rnpv_valuation(ticker, info)

        fcfs, pv_fcf = [], 0.0
        r_rev = revenue
        for yr, growth in enumerate(g, 1):
            r_rev *= (1 + growth)
            fcf    = r_rev * op_margin * (1 - tax_rate) * (1 - capex_pct)
            pv     = fcf / (1 + wacc) ** yr
            fcfs.append(fcf)
            pv_fcf += pv

        tv    = fcfs[-1] * (1 + terminal_g) / (wacc - terminal_g)
        pv_tv = tv / (1 + wacc) ** 5

        total_pv      = pv_fcf + pv_tv
        implied_price = total_pv / shares_out
        upside        = (implied_price / current_px - 1) if current_px else None

        return {
            "impliedSharePrice": round(implied_price, 2),
            "upside":            round(upside, 4) if upside is not None else None,
            "currencySymbol":    _currency_symbol(currency),
            "valuationMethod":   "DCF",
            "dcf": {
                "revenueGrowthY1": g[0], "revenueGrowthY2": g[1],
                "revenueGrowthY3": g[2], "revenueGrowthY4": g[3],
                "revenueGrowthY5": g[4],
                "wacc":            wacc,
                "terminalGrowth":  terminal_g,
                "operatingMargin": op_margin,
                "taxRate":         tax_rate,
                "capexPercent":    capex_pct,
            },
        }
    except Exception as exc:
        logger.error("_run_dcf(%s): %s", ticker, exc)
        return {"impliedSharePrice": None, "upside": None, "dcf": assumptions}


def _default_assumptions(ticker: str) -> dict:
    try:
        info = df_mod._cached_yf_info(ticker)
        rev_growth = _safe(info.get("revenueGrowth"), 0.10)
        # Cap the seed so an outlier trailing growth figure doesn't drive a runaway DCF.
        rev_growth = min(max(rev_growth, -0.5), 0.40)
        op_margin  = _safe(info.get("operatingMargins"), 0.20)
        return {
            "revenueGrowthY1": max(rev_growth, -0.5),
            "revenueGrowthY2": max(rev_growth * 0.85, -0.5),
            "revenueGrowthY3": max(rev_growth * 0.70, -0.5),
            "revenueGrowthY4": max(rev_growth * 0.55, -0.5),
            "revenueGrowthY5": max(rev_growth * 0.40, -0.5),
            "wacc":            0.10,
            "terminalGrowth":  0.03,
            "operatingMargin": max(op_margin, 0.05),
            "taxRate":         0.21,
            "capexPercent":    0.05,
        }
    except Exception:
        return {
            "revenueGrowthY1": 0.15, "revenueGrowthY2": 0.12,
            "revenueGrowthY3": 0.10, "revenueGrowthY4": 0.08,
            "revenueGrowthY5": 0.06, "wacc": 0.10,
            "terminalGrowth": 0.03, "operatingMargin": 0.20,
            "taxRate": 0.21, "capexPercent": 0.05,
        }


@app.get("/api/dcf/{ticker}")
def get_dcf(ticker: str):
    assumptions = _default_assumptions(ticker)
    return _to_json_safe(_run_dcf(ticker, assumptions))


@app.post("/api/dcf/{ticker}")
def update_dcf(ticker: str, body: dict):
    assumptions = {**_default_assumptions(ticker), **body}
    return _to_json_safe(_run_dcf(ticker, assumptions))


# ============================================================
# /api/rnpv/{ticker}  — standalone pipeline rNPV valuation
# ============================================================

@app.get("/api/rnpv/{ticker}")
def get_rnpv(ticker: str):
    try:
        info = df_mod._cached_yf_info(ticker)
        return _rnpv_valuation(ticker, info)
    except Exception as exc:
        logger.error("rnpv(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/scenarios/{ticker}  — 3-scenario + Monte Carlo
# ============================================================

@app.get("/api/scenarios/{ticker}")
def get_scenarios(ticker: str):
    try:
        info     = df_mod._cached_yf_info(ticker)
        currency = info.get("currency", "USD")
        sym      = _currency_symbol(currency)
        current  = _safe(info.get("regularMarketPrice") or info.get("currentPrice"), 0)
        beta     = _safe(info.get("beta"), 1.0)
        target   = _safe(info.get("targetMeanPrice"), 0)
        target_h = _safe(info.get("targetHighPrice"), 0)
        target_l = _safe(info.get("targetLowPrice"), 0)

        if not current:
            hist = df_mod.get_price_history(ticker, period="5d")
            current = float(hist["Close"].iloc[-1]) if not hist.empty else 100.0

        bull_px  = target_h if target_h else current * 1.45
        base_px  = target   if target   else current * 1.15
        bear_px  = target_l if target_l else current * 0.70

        scenarios = [
            {"label": "Bull", "targetPrice": round(bull_px, 2),
             "returnPct": round((bull_px / current - 1) * 100, 1), "probability": 0.25},
            {"label": "Base", "targetPrice": round(base_px, 2),
             "returnPct": round((base_px / current - 1) * 100, 1), "probability": 0.50},
            {"label": "Bear", "targetPrice": round(bear_px, 2),
             "returnPct": round((bear_px / current - 1) * 100, 1), "probability": 0.25},
        ]

        # Monte Carlo (1 year, 1000 simulations)
        hist = df_mod.get_price_history(ticker, period="1y")
        daily_vol = 0.02  # default
        if not hist.empty and len(hist) > 20:
            daily_vol = float(hist["Close"].pct_change().dropna().std())
        # Clamp vol and beta to prevent simulation overflow / nan propagation
        daily_vol = min(max(float(daily_vol) if math.isfinite(daily_vol) else 0.02, 0.005), 0.08)
        try:
            beta_val = min(abs(float(beta)), 2.5)
        except (TypeError, ValueError):
            beta_val = 1.0

        np.random.seed(42)
        n_sim, n_days = 1000, 252
        # Clip daily returns so individual steps can never go below -50%
        daily_returns = np.clip(
            np.random.normal(0, daily_vol * beta_val, (n_sim, n_days)),
            -0.5, 0.5,
        )
        final_prices = current * np.prod(1 + daily_returns, axis=1)
        # Replace any non-finite or non-positive prices with the starting price
        final_prices = np.where(
            np.isfinite(final_prices) & (final_prices > 0), final_prices, current
        )

        def _safe_round(v: float) -> float:
            """Return v rounded to 2dp; fall back to 0.0 if not finite."""
            return round(v, 2) if math.isfinite(v) and v > 0 else 0.0

        # Build 100 representative simulation paths (every 10th sim, 51 points each)
        sim_paths = []
        for r in daily_returns[::10]:
            path: list[float] = []
            for d in range(0, n_days, 5):
                prod = float(np.prod(1 + r[:d])) if d > 0 else 1.0
                p = current * prod
                path.append(_safe_round(p))
            sim_paths.append(path)

        mc = {
            "percentile5":  _safe_round(float(np.percentile(final_prices, 5))),
            "percentile25": _safe_round(float(np.percentile(final_prices, 25))),
            "median":       _safe_round(float(np.median(final_prices))),
            "percentile75": _safe_round(float(np.percentile(final_prices, 75))),
            "percentile95": _safe_round(float(np.percentile(final_prices, 95))),
            "simulations":  sim_paths,
        }

        return _to_json_safe({
            "currentPrice":  round(current, 2),
            "currencySymbol": sym,
            "scenarios":     scenarios,
            "monteCarlo":    mc,
        })
    except Exception as exc:
        logger.error("scenarios(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/search?q={query}  — ticker search
# ============================================================

@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    try:
        results = yf.Search(q, max_results=8)
        quotes  = []
        for item in (results.quotes or []):
            quotes.append({
                "symbol":    item.get("symbol", ""),
                "shortname": item.get("shortname") or item.get("longname", ""),
                "exchange":  item.get("exchange", ""),
                "quoteType": item.get("quoteType", ""),
            })
        return {"quotes": quotes}
    except Exception as exc:
        logger.warning("search(%s): %s", q, exc)
        return {"quotes": []}


# ============================================================
# /api/watchlist  — persistent watchlist (GET / POST / DELETE)
# ============================================================

@app.get("/api/watchlist")
def get_watchlist():
    return _load_watchlist()


def _add_watchlist_symbol(symbol: str) -> list[str]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    wl = _load_watchlist()
    if symbol not in wl:
        if len(wl) >= 50:
            raise HTTPException(status_code=400, detail="Watchlist limit of 50 tickers reached")
        wl.append(symbol)
        _save_watchlist(wl)
    return wl


@app.post("/api/watchlist")
def add_to_watchlist(body: dict):
    wl = _add_watchlist_symbol(body.get("symbol") or body.get("ticker") or "")
    return {"watchlist": wl}


@app.post("/api/watchlist/{ticker}")
def add_to_watchlist_path(ticker: str):
    """Path-param variant used by the SPA (POST /api/watchlist/{ticker})."""
    wl = _add_watchlist_symbol(ticker)
    return {"watchlist": wl}


@app.delete("/api/watchlist/{ticker}")
def remove_from_watchlist(ticker: str):
    wl = _load_watchlist()
    wl = [t for t in wl if t.upper() != ticker.upper()]
    _save_watchlist(wl)
    return {"watchlist": wl}


# ============================================================
# /api/dual-listing/{ticker}  — cross-border premium/discount
# ============================================================

@app.get("/api/dual-listing/{ticker}")
def get_dual_listing(ticker: str):
    try:
        result = get_dual_listing_info(ticker)
        if result is None:
            return {"dual_listed": False, "status": "none", "ticker": ticker.upper()}
        return {"dual_listed": True, **result}
    except Exception as exc:
        logger.error("dual_listing(%s): %s", ticker, exc)
        return {"dual_listed": False, "status": "none", "ticker": ticker.upper()}


# ============================================================
# /api/pipeline-summary/{ticker}  — LLM pipeline risk summarisation
# ============================================================

@app.get("/api/pipeline-summary/{ticker}")
def get_pipeline_summary(ticker: str):
    try:
        raw     = fetch_clinicaltrials(ticker)
        enriched = enrich_trials(raw) if not raw.empty else raw
        try:
            info         = df_mod._cached_yf_info(ticker)
            company_name = info.get("longName") or info.get("shortName") or ticker
        except Exception:
            company_name = ticker
        result = summarize_pipeline(enriched, company_name)
        return result
    except Exception as exc:
        logger.error("pipeline_summary(%s): %s", ticker, exc)
        return {
            "summary": "Pipeline summary unavailable.",
            "key_risks": [],
            "upcoming_catalysts": [],
            "ai_generated": False,
        }


# ============================================================
# /api/debug/llm  — diagnose LLM provider configuration
# ============================================================

@app.get("/api/debug/llm")
def debug_llm():
    """
    Returns which LLM keys are detected and whether a minimal test call succeeds.
    Safe to expose: API key values are never returned, only their presence/prefix.
    """
    import llm_analysis as _llm

    def _mask(key_name: str) -> str:
        val = os.getenv(key_name, "")
        if not val:
            return "NOT SET"
        return val[:8] + "..." + f" ({len(val)} chars)"

    status = {
        "ANTHROPIC_API_KEY":  _mask("ANTHROPIC_API_KEY"),
        "GEMINI_API_KEY":     _mask("GEMINI_API_KEY"),
        "GROQ_API_KEY":       _mask("GROQ_API_KEY"),
        "OPENROUTER_API_KEY": _mask("OPENROUTER_API_KEY"),
        "GEMINI_MODEL":       os.getenv("GEMINI_MODEL", "gemini-1.5-flash (default)"),
        "any_llm_detected":   _llm._has_any_llm(),
    }

    # Attempt a minimal LLM call
    if _llm._has_any_llm():
        try:
            raw = _llm._llm_call(
                "You are a test assistant. Reply with valid JSON only.",
                'Return exactly: {"ok": true}',
                max_tokens=20,
            )
            status["test_call"] = "SUCCESS"
            status["test_response"] = raw[:200]
        except Exception as exc:
            status["test_call"] = "FAILED"
            status["test_error"] = str(exc)
    else:
        status["test_call"] = "SKIPPED — no LLM key set"

    return status


# ============================================================
# /api/pipeline-research/{ticker}  — LLM-powered comprehensive pipeline research
# ============================================================

@app.get("/api/pipeline-research/{ticker}")
def get_pipeline_research(ticker: str):
    """
    AI-powered pipeline research: returns ALL known programs (owned + partnered +
    in-licensed), with TAM estimates and competitive context, regardless of whether
    trials are registered under the company's own name on ClinicalTrials.gov.

    Then enriches any returned NCT IDs with live CT.gov data for current status
    and enrollment figures.
    """
    try:
        ticker = ticker.upper()
        try:
            info         = df_mod._cached_yf_info(ticker)
            company_name = info.get("longName") or info.get("shortName") or ticker
        except Exception:
            company_name = ticker

        result = research_full_pipeline(ticker, company_name)

        # Enrich with live CT.gov data for any NCT IDs the LLM returned
        all_nct_ids = []
        for prog in result.get("programs", []):
            all_nct_ids.extend(prog.get("nct_ids") or [])

        if all_nct_ids:
            live_df = fetch_clinicaltrials_by_nct_ids(all_nct_ids)
            live_map: dict = {}
            if not live_df.empty:
                for _, row in live_df.iterrows():
                    nid = row.get("nct_id")
                    if nid:
                        live_map[nid] = {
                            "status":      row.get("status"),
                            "enrollment":  row.get("enrollment"),
                            "start_date":  row.get("start_date"),
                            "completion":  row.get("primary_completion_date"),
                            "ct_title":    row.get("title"),
                            "ct_sponsor":  row.get("sponsor"),
                        }
            for prog in result.get("programs", []):
                ct_enrichments = [live_map[nid] for nid in (prog.get("nct_ids") or []) if nid in live_map]
                if ct_enrichments:
                    prog["ct_data"] = ct_enrichments[0]  # primary NCT enrichment
                    # Prefer live CT.gov status over LLM guess
                    if ct_enrichments[0].get("status"):
                        prog["ct_status"] = ct_enrichments[0]["status"]
                        prog["ct_enrollment"] = ct_enrichments[0]["enrollment"]

        result["ticker"] = ticker
        result["company_name"] = company_name
        return result

    except Exception as exc:
        logger.error("pipeline_research(%s): %s", ticker, exc)
        return {
            "programs": [],
            "pipeline_summary": f"Pipeline research unavailable: {exc}",
            "hk_china_angle": "",
            "data_note": "",
            "ai_generated": False,
            "ticker": ticker,
        }


# ============================================================
# /api/filings/{ticker}  — HKEXnews announcements (HK) / news proxy (US)
# ============================================================

@app.get("/api/filings/{ticker}")
def get_filings(ticker: str):
    try:
        df = df_mod.get_filings(ticker, limit=50)
        if df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            records.append({
                "date":  str(row.get("date") or ""),
                "title": str(row.get("title") or ""),
                "type":  str(row.get("type") or ""),
                "url":   str(row.get("url") or ""),
            })
        return records
    except Exception as exc:
        logger.error("filings(%s): %s", ticker, exc)
        return []


# ============================================================
# /api/flow/{ticker}  — CCASS shareholding snapshots (HK)
# ============================================================

# Confidence results — cache per ticker for 5 minutes (ML training + LLM call are expensive)
_CONFIDENCE_CACHE: dict[str, tuple[dict, float]] = {}
_CONFIDENCE_CACHE_TTL = 300  # seconds

# CCASS data changes monthly — cache each ticker for 1 hour so repeated loads are instant
_FLOW_CACHE: dict[str, tuple[list, float]] = {}
_FLOW_CACHE_TTL = 3600  # seconds


@app.get("/api/flow/{ticker}")
def get_flow(ticker: str):
    key = ticker.upper()
    now = time.monotonic()
    cached, ts = _FLOW_CACHE.get(key, (None, 0.0))
    if cached is not None and now - ts < _FLOW_CACHE_TTL:
        return cached
    try:
        df = df_mod.get_institutional_flow(ticker)
        if df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            records.append({
                "participant_id":   str(row.get("participant_id") or ""),
                "participant_name": str(row.get("participant_name") or ""),
                "shares":           int(row["shares"]) if pd.notna(row.get("shares")) else None,
                "percentage":       float(row["percentage"]) if pd.notna(row.get("percentage")) else None,
                "snapshot_date":    str(row.get("snapshot_date") or ""),
            })
        _FLOW_CACHE[key] = (records, now)
        return records
    except Exception as exc:
        logger.error("flow(%s): %s", ticker, exc)
        return []


# ============================================================
# /api/sources/{ticker}  — research shortcut URLs
# ============================================================

@app.get("/api/sources/{ticker}")
def get_sources(ticker: str):
    """Return curated deep-link URLs for every data source relevant to this ticker."""
    try:
        info = df_mod._cached_yf_info(ticker)
        company_name = (info.get("longName") or info.get("shortName") or ticker).strip()
    except Exception:
        company_name = ticker

    name_q = _url_quote(company_name)
    is_hk  = ticker.upper().endswith(".HK")

    sources: dict[str, str] = {
        "clinicaltrials_url": (
            f"https://clinicaltrials.gov/search?query={name_q}&aggFilters=studyType:int"
        ),
        "who_ictrp_url": (
            f"https://trialsearch.who.int/AdvSearch.aspx?SearchTerms={name_q}"
        ),
    }

    if is_hk:
        raw_code = ticker.upper().replace(".HK", "").lstrip("0") or "0"
        hk_code  = f"{int(raw_code):04d}"
        sources["hkexnews_url"] = (
            f"https://www1.hkexnews.hk/search/titlesearch.xhtml?r=&kw={hk_code}"
        )
        sources["nmpa_url"]  = "https://www.nmpa.gov.cn/"
        sources["ctctr_url"] = "http://www.chinadrugtrials.org.cn/index.html"
        sources["yicai_url"] = f"https://www.yicai.com/search/?keywords={name_q}"
    else:
        ticker_q = _url_quote(ticker.upper())
        sources["sec_edgar_url"] = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&company={ticker_q}&type=10-K&dateb=&owner=include&count=10"
        )

    return {"ticker": ticker.upper(), "company": company_name, "sources": sources}


# ============================================================
# /api/backtest/{ticker}  — RSI+MACD strategy backtest
# ============================================================

_BACKTEST_CACHE: dict[str, tuple[dict, float]] = {}
_BACKTEST_CACHE_TTL = 3600  # hourly — price-derived, stable intraday


@app.get("/api/backtest/{ticker}")
def get_backtest(ticker: str, period: str = "2y"):
    key = f"{ticker.upper()}:{period}"
    now = time.monotonic()
    cached, ts = _BACKTEST_CACHE.get(key, (None, 0.0))
    if cached is not None and now - ts < _BACKTEST_CACHE_TTL:
        return cached
    try:
        prices = df_mod.get_price_history(ticker, period=period)
        if prices.empty or len(prices) < 50:
            raise HTTPException(status_code=502, detail="Insufficient price history")
        result = _backtester.run_backtest(prices)
        equity = [
            {"date": str(idx.date()), "value": round(float(v), 2)}
            for idx, v in result.equity_curve.items()
            if not math.isnan(float(v))
        ]
        trades = []
        if not result.trade_log.empty:
            for _, row in result.trade_log.tail(50).iterrows():
                trades.append({
                    "entryDate":  str(row["entry_date"].date()) if hasattr(row["entry_date"], "date") else str(row["entry_date"]),
                    "exitDate":   str(row["exit_date"].date())  if hasattr(row["exit_date"],  "date") else str(row["exit_date"]),
                    "entryPrice": round(float(row["entry_price"]), 4),
                    "exitPrice":  round(float(row["exit_price"]),  4),
                    "pnlPct":     round(float(row["pnl_pct"]), 2),
                    "holdDays":   int(row["hold_days"]),
                    "exitReason": row["exit_reason"],
                })
        payload = _to_json_safe({
            "metrics":     result.metrics,
            "equityCurve": equity,
            "trades":      trades,
            "ticker":      ticker.upper(),
            "period":      period,
        })
        _BACKTEST_CACHE[key] = (payload, time.monotonic())
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("backtest(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/screen  — alpha screener
# ============================================================

_SCREEN_CACHE: dict[str, tuple[dict, float]] = {}
_SCREEN_CACHE_TTL = 1800  # 30 minutes


@app.get("/api/screen")
def get_screen(region: str = "HK"):
    region = region.upper()
    if region not in ("HK", "US"):
        raise HTTPException(status_code=400, detail="region must be HK or US")
    now = time.monotonic()
    cached, ts = _SCREEN_CACHE.get(region, (None, 0.0))
    if cached is not None and now - ts < _SCREEN_CACHE_TTL:
        return cached
    try:
        df = _screener.run_screen(region=region, top_n=15)
        if df.empty:
            return {"region": region, "results": [], "cachedAt": None}
        results = []
        for _, row in df.iterrows():
            results.append(_to_json_safe({
                "rank":         int(row["rank"]),
                "ticker":       row["ticker"],
                "totalScore":   row["total_score"],
                "momentum":     row["momentum"],
                "value":        row["value"],
                "pipeline":     row["pipeline"],
                "quality":      row["quality"],
                "technical":    row["technical"],
                "marketCap":    row.get("market_cap"),
                "psRatio":      row.get("ps_ratio"),
                "revenueGrowth":row.get("revenue_growth"),
            }))
        payload = {
            "region":   region,
            "results":  results,
            "cachedAt": datetime.utcnow().isoformat() + "Z",
        }
        _SCREEN_CACHE[region] = (payload, time.monotonic())
        return payload
    except Exception as exc:
        logger.error("screen(%s): %s", region, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/risk/{ticker}  — bear-case risk factor analysis
# ============================================================

_RISK_CACHE: dict[str, tuple[dict, float]] = {}
_RISK_CACHE_TTL = 1800


@app.get("/api/risk/{ticker}")
def get_risk(ticker: str):
    key = ticker.upper()
    now = time.monotonic()
    cached, ts = _RISK_CACHE.get(key, (None, 0.0))
    if cached is not None and now - ts < _RISK_CACHE_TTL:
        return cached
    try:
        prices = df_mod.get_price_history(ticker, period="1y")
        funds  = df_mod.get_financial_metrics(ticker)
        trials_raw = fetch_clinicaltrials(ticker)
        trials = enrich_trials(trials_raw) if not trials_raw.empty else trials_raw
        info   = df_mod._cached_yf_info(ticker)
        risks  = _devil.analyse(ticker, prices, funds, trials, info)
        summary = _devil.risk_summary(risks)
        factors = [
            {
                "category": r.category,
                "title":    r.title,
                "detail":   r.detail,
                "severity": r.severity,
                "evidence": r.evidence,
            }
            for r in risks
        ]
        payload = {"ticker": key, "summary": summary, "factors": factors}
        _RISK_CACHE[key] = (payload, time.monotonic())
        return payload
    except Exception as exc:
        logger.error("risk(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# /api/earnings/{ticker}  — EPS history + analyst targets
# ============================================================

@app.get("/api/earnings/{ticker}")
def get_earnings(ticker: str):
    try:
        data = _earnings.earnings_summary(ticker)
        eps_df = data.get("quarterly_eps_df")
        rev_df = data.get("annual_revenue_df")

        quarterly_eps = []
        if eps_df is not None and not eps_df.empty:
            for _, row in eps_df.iterrows():
                quarterly_eps.append(_to_json_safe({
                    "date":       str(row.get("Date", row.index if hasattr(row, "index") else "")),
                    "reported":   row.get("Reported EPS"),
                    "estimated":  row.get("Estimated EPS"),
                    "surprisePct":row.get("Surprise %"),
                    "beat":       bool(row["Beat"]) if "Beat" in row and row["Beat"] is not None else None,
                }))

        annual_revenue = []
        if rev_df is not None and not rev_df.empty:
            for _, row in rev_df.iterrows():
                annual_revenue.append(_to_json_safe({
                    "date":       str(row.get("Date", "")),
                    "revenue":    row.get("Revenue"),
                    "yoyGrowthPct": row.get("YoY Growth %"),
                }))

        return _to_json_safe({
            "ticker":           ticker.upper(),
            "nextEarningsDate": data.get("next_earnings_date"),
            "beatRate8q":       data.get("beat_rate_8q"),
            "avgSurprisePct":   data.get("avg_surprise_pct"),
            "revenueCagr3y":    data.get("revenue_cagr_3y"),
            "targetMean":       data.get("target_mean"),
            "targetHigh":       data.get("target_high"),
            "targetLow":        data.get("target_low"),
            "recommendation":   data.get("recommendation"),
            "nAnalysts":        data.get("n_analysts"),
            "quarterlyEps":     quarterly_eps,
            "annualRevenue":    annual_revenue,
        })
    except Exception as exc:
        logger.error("earnings(%s): %s", ticker, exc)
        raise HTTPException(status_code=502, detail=str(exc))


# ============================================================
# Static files  — React SPA  (MUST be last)
# ============================================================

# Serve /assets/* directly
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")


@app.get("/favicon.png", include_in_schema=False)
async def favicon():
    fp = BASE_DIR / "favicon.png"
    if fp.exists():
        return FileResponse(str(fp))
    raise HTTPException(status_code=404)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Catch-all: return index.html for any unknown path (SPA client-side routing)."""
    return FileResponse(str(BASE_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
