"""
data_fetcher.py — central data layer for BioTerminal Pro.

Structure
---------
SECTION 1 : Low-level primitives  (called by exchange adapters)
SECTION 2 : Adapter factory        (get_adapter_for_ticker)
SECTION 3 : High-level public API  (called by app.py and analysis modules)
             All high-level functions route through the adapter, then fall
             back to direct helpers for regions that don't override a method.

Adding a new region
-------------------
1. Add ConcreteAdapter in exchanges/
2. Register it in exchanges/__init__.get_exchange_adapter()
3. No changes required here unless the region needs a new primitive.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from utils import clean_ohlcv, period_to_dates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory TTL cache for yfinance .info calls (60-second TTL)
# ---------------------------------------------------------------------------

_INFO_CACHE: dict[str, tuple[dict, float]] = {}
_INFO_CACHE_LOCK = Lock()
_INFO_CACHE_TTL = 60  # seconds


def _cached_yf_info(ticker: str) -> dict:
    now = time.monotonic()
    with _INFO_CACHE_LOCK:
        if ticker in _INFO_CACHE:
            value, ts = _INFO_CACHE[ticker]
            if now - ts < _INFO_CACHE_TTL:
                return value
    info = yf.Ticker(ticker).info or {}
    with _INFO_CACHE_LOCK:
        _INFO_CACHE[ticker] = (info, now)
    return info


# ClinicalTrials.gov REST API v2
_CT_BASE = "https://clinicaltrials.gov/api/v2/studies"
_CT_FIELDS = (
    "NCTId,BriefTitle,OverallStatus,Phase,Condition,"
    "LeadSponsorName,StartDate,PrimaryCompletionDate,EnrollmentCount"
)

# yfinance info keys we care about for the metadata dict
_META_KEYS = [
    "shortName", "longName", "sector", "industry", "longBusinessSummary",
    "exchange", "currency", "country", "website", "fullTimeEmployees",
    "marketCap", "logo_url",
]

# yfinance info keys for fundamentals
_FUND_KEYS = [
    "trailingPE", "priceToBook", "priceToSalesTrailing12Months",
    "enterpriseToEbitda", "enterpriseToRevenue", "marketCap",
    "enterpriseValue", "totalRevenue", "grossProfits", "ebitda",
    "netIncomeToCommon", "totalCash", "totalDebt", "beta",
    "dividendYield", "sharesOutstanding", "floatShares",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "averageVolume",
    "forwardPE", "pegRatio", "returnOnEquity", "returnOnAssets",
    "operatingMargins", "profitMargins", "revenueGrowth",
    "earningsGrowth", "currentRatio", "debtToEquity",
]


# ============================================================
# SECTION 1 — Low-level primitives  (used by adapters)
# ============================================================

def fetch_yfinance_prices(
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLCV from yfinance and return a clean DataFrame."""
    try:
        raw = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            logger.warning("yfinance returned empty prices for %s", ticker)
            return pd.DataFrame()
        return clean_ohlcv(raw)
    except Exception as exc:
        logger.error("fetch_yfinance_prices(%s): %s", ticker, exc)
        return pd.DataFrame()


def fetch_yfinance_metadata(ticker: str) -> dict:
    """Return company metadata from yfinance .info (cached 60s)."""
    try:
        info = _cached_yf_info(ticker)
    except Exception as exc:
        logger.error("fetch_yfinance_metadata(%s): %s", ticker, exc)
        info = {}

    return {
        "name":        info.get("longName") or info.get("shortName", ticker),
        "short_name":  info.get("shortName", ticker),
        "sector":      info.get("sector"),
        "industry":    info.get("industry"),
        "description": info.get("longBusinessSummary"),
        "exchange":    info.get("exchange"),
        "currency":    info.get("currency", "USD"),
        "country":     info.get("country"),
        "website":     info.get("website"),
        "employees":   info.get("fullTimeEmployees"),
        "market_cap":  info.get("marketCap"),
        "logo_url":    info.get("logo_url"),
    }


def fetch_yfinance_fundamentals(ticker: str) -> dict:
    """Return a flat dict of financial ratios / key metrics from yfinance .info (cached 60s)."""
    try:
        info = _cached_yf_info(ticker)
    except Exception as exc:
        logger.error("fetch_yfinance_fundamentals(%s): %s", ticker, exc)
        info = {}

    return {
        "pe_ratio":         info.get("trailingPE"),
        "forward_pe":       info.get("forwardPE"),
        "pb_ratio":         info.get("priceToBook"),
        "ps_ratio":         info.get("priceToSalesTrailing12Months"),
        "ev_ebitda":        info.get("enterpriseToEbitda"),
        "ev_revenue":       info.get("enterpriseToRevenue"),
        "market_cap":       info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "revenue_ttm":      info.get("totalRevenue"),
        "gross_profit_ttm": info.get("grossProfits"),
        "ebitda_ttm":       info.get("ebitda"),
        "net_income_ttm":   info.get("netIncomeToCommon"),
        "cash":             info.get("totalCash"),
        "total_debt":       info.get("totalDebt"),
        "beta":             info.get("beta"),
        "dividend_yield":   info.get("dividendYield"),
        "shares_out":       info.get("sharesOutstanding"),
        "float_shares":     info.get("floatShares"),
        "52wk_high":        info.get("fiftyTwoWeekHigh"),
        "52wk_low":         info.get("fiftyTwoWeekLow"),
        "avg_volume_30d":   info.get("averageVolume"),
        "peg_ratio":        info.get("pegRatio"),
        "roe":              info.get("returnOnEquity"),
        "roa":              info.get("returnOnAssets"),
        "operating_margin": info.get("operatingMargins"),
        "profit_margin":    info.get("profitMargins"),
        "revenue_growth":   info.get("revenueGrowth"),
        "earnings_growth":  info.get("earningsGrowth"),
        "current_ratio":    info.get("currentRatio"),
        "debt_to_equity":   info.get("debtToEquity"),
    }


def fetch_yfinance_news(ticker: str, limit: int = 50) -> pd.DataFrame:
    """Fetch recent news from yfinance and return a normalised DataFrame.

    yfinance ≥ 0.2.50 wraps each item under item['content'] with a nested
    provider/canonicalUrl structure.  Older versions had flat top-level keys.
    This function handles both layouts.
    """
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
    except Exception as exc:
        logger.error("fetch_yfinance_news(%s): %s", ticker, exc)
        news = []

    rows = []
    for item in news[:limit]:
        # New nested layout (yfinance ≥ ~0.2.50)
        if "content" in item and isinstance(item["content"], dict):
            c   = item["content"]
            pub = c.get("pubDate") or c.get("displayTime")
            url = (c.get("canonicalUrl") or {}).get("url") or \
                  (c.get("clickThroughUrl") or {}).get("url", "")
            rows.append({
                "date":    pub,
                "title":   c.get("title", ""),
                "source":  (c.get("provider") or {}).get("displayName", ""),
                "url":     url,
                "summary": c.get("summary") or c.get("description", ""),
            })
        else:
            # Legacy flat layout
            pub = item.get("providerPublishTime") or item.get("published")
            if pub and isinstance(pub, (int, float)):
                pub = datetime.fromtimestamp(pub)
            rows.append({
                "date":    pub,
                "title":   item.get("title", ""),
                "source":  item.get("publisher", ""),
                "url":     item.get("link", ""),
                "summary": item.get("summary", ""),
            })

    return pd.DataFrame(rows, columns=["date", "title", "source", "url", "summary"])


def fetch_clinicaltrials(ticker: str) -> pd.DataFrame:
    """
    Look up company name from yfinance, generate multiple name variants, then
    search ClinicalTrials.gov as both sponsor and collaborator. Deduplicates by NCT ID.
    """
    try:
        meta = fetch_yfinance_metadata(ticker)
        company_name = meta.get("name") or ticker
        variants = _ct_name_variants(company_name)
        return fetch_clinicaltrials_multi(variants)
    except Exception as exc:
        logger.error("fetch_clinicaltrials(%s): %s", ticker, exc)
        return _empty_trials_df()


def _ct_name_variants(company_name: str) -> list[str]:
    """Generate search term variants by progressively stripping corporate suffixes."""
    suffixes = re.compile(
        r"\s+(Inc\.?|Corp\.?|Ltd\.?|LLC\.?|PLC\.?|S\.A\.?|A\.G\.?|AG|"
        r"Holdings?|Holding|Therapeutics?|Biosciences?|Pharmaceuticals?|"
        r"Biopharma|Biotech|Oncology|Sciences?|Medical|Biopharmaceuticals?)$",
        flags=re.IGNORECASE,
    )
    seen: list[str] = []
    current = company_name.strip()
    while True:
        if current and current not in seen:
            seen.append(current)
        stripped = suffixes.sub("", current).strip()
        if stripped == current or not stripped:
            break
        current = stripped
    # Also add a version dropping everything after the first comma or parenthesis
    base = re.split(r"[,(]", company_name)[0].strip()
    if base and base not in seen:
        seen.append(base)
    return seen[:4]  # cap at 4 queries to avoid rate-limiting


def fetch_clinicaltrials_multi(search_terms: list[str], page_size: int = 50) -> pd.DataFrame:
    """
    Search ClinicalTrials.gov with multiple terms (sponsor field + general term),
    deduplicating results by NCT ID.
    """
    seen_ids: set[str] = set()
    all_rows: list[dict] = []

    for term in search_terms:
        for field in ("query.spons", "query.term"):
            rows = _ct_search_raw(term, field, page_size)
            for row in rows:
                nct = row.get("nct_id")
                if nct and nct not in seen_ids:
                    seen_ids.add(nct)
                    all_rows.append(row)

    return pd.DataFrame(all_rows) if all_rows else _empty_trials_df()


def fetch_clinicaltrials_by_nct_ids(nct_ids: list[str]) -> pd.DataFrame:
    """
    Fetch clinical trial details for a specific list of NCT IDs.
    Used to enrich LLM-discovered programs with live CT.gov data.
    """
    if not nct_ids:
        return _empty_trials_df()
    filter_expr = " OR ".join(f"AREA[NCTId]{nid}" for nid in nct_ids[:20])
    rows = _ct_search_raw(filter_expr, "filter.advanced", len(nct_ids) + 5)
    return pd.DataFrame(rows) if rows else _empty_trials_df()


def _ct_search_raw(term: str, field: str, page_size: int) -> list[dict]:
    """Single ClinicalTrials.gov query; returns list of row dicts."""
    params = {
        field:        term,
        "fields":     _CT_FIELDS,
        "format":     "json",
        "pageSize":   page_size,
    }
    try:
        resp = requests.get(_CT_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("_ct_search_raw(%s, %s): %s", field, term[:40], exc)
        return []

    rows = []
    for study in data.get("studies", []):
        ps       = study.get("protocolSection", {})
        id_mod   = ps.get("identificationModule", {})
        stat_mod = ps.get("statusModule", {})
        design   = ps.get("designModule", {})
        cond_mod = ps.get("conditionsModule", {})
        spon_mod = ps.get("sponsorCollaboratorsModule", {})

        phases    = design.get("phases", [])
        phase_str = ", ".join(p.replace("PHASE", "Phase ") for p in phases) if phases else "N/A"

        rows.append({
            "nct_id":                  id_mod.get("nctId"),
            "title":                   id_mod.get("briefTitle"),
            "phase":                   phase_str,
            "status":                  stat_mod.get("overallStatus"),
            "condition":               ", ".join(cond_mod.get("conditions", [])),
            "start_date":              _ct_date(stat_mod.get("startDateStruct")),
            "primary_completion_date": _ct_date(stat_mod.get("primaryCompletionDateStruct")),
            "enrollment":              design.get("enrollmentInfo", {}).get("count"),
            "sponsor":                 spon_mod.get("leadSponsor", {}).get("name"),
        })
    return rows


def fetch_clinicaltrials_by_sponsor(sponsor_name: str, page_size: int = 50) -> pd.DataFrame:
    """Legacy single-term search kept for backward compatibility."""
    rows = _ct_search_raw(sponsor_name, "query.spons", page_size)
    return pd.DataFrame(rows) if rows else _empty_trials_df()


def _ct_date(struct: Optional[dict]) -> Optional[str]:
    if not struct:
        return None
    return struct.get("date")


def _empty_trials_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "nct_id", "title", "phase", "status", "condition",
            "start_date", "primary_completion_date", "enrollment", "sponsor",
        ]
    )


# ============================================================
# SECTION 2 — Adapter factory
# ============================================================

def get_adapter_for_ticker(ticker: str):
    """Return the exchange adapter for the given ticker (lazy import)."""
    from exchanges import get_exchange_adapter
    return get_exchange_adapter(ticker)


# ============================================================
# SECTION 3 — High-level public API  (called by app.py / modules)
# ============================================================

def get_price_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV history.  Uses the exchange adapter to route to the correct
    data source; falls back to direct yfinance if the adapter raises.
    """
    if start is None or end is None:
        start, end = period_to_dates(period)
    adapter = get_adapter_for_ticker(ticker)
    try:
        df = adapter.get_prices(ticker, start, end, interval)
        if not df.empty:
            return df
    except NotImplementedError:
        pass
    return fetch_yfinance_prices(ticker, start, end, interval)


def get_company_info(ticker: str) -> dict:
    adapter = get_adapter_for_ticker(ticker)
    try:
        return adapter.get_metadata(ticker)
    except Exception as exc:
        logger.error("get_company_info(%s): %s", ticker, exc)
        return {"name": ticker, "currency": "USD"}


def get_financial_metrics(ticker: str) -> dict:
    adapter = get_adapter_for_ticker(ticker)
    try:
        return adapter.get_fundamentals(ticker)
    except Exception as exc:
        logger.error("get_financial_metrics(%s): %s", ticker, exc)
        return {}


def get_news_feed(ticker: str, limit: int = 20) -> pd.DataFrame:
    adapter = get_adapter_for_ticker(ticker)
    try:
        df = adapter.get_news(ticker, limit)
        if not df.empty:
            return df
    except NotImplementedError:
        pass
    return fetch_yfinance_news(ticker, limit)


def get_pipeline_data(ticker: str) -> pd.DataFrame:
    adapter = get_adapter_for_ticker(ticker)
    try:
        df = adapter.get_trials(ticker)
        if not df.empty:
            return df
    except NotImplementedError:
        pass
    return fetch_clinicaltrials(ticker)


def get_filings(ticker: str, limit: int = 20) -> pd.DataFrame:
    adapter = get_adapter_for_ticker(ticker)
    try:
        return adapter.get_filings(ticker, limit)
    except NotImplementedError:
        return pd.DataFrame(columns=["date", "title", "type", "url"])


def get_institutional_flow(ticker: str) -> pd.DataFrame:
    adapter = get_adapter_for_ticker(ticker)
    try:
        return adapter.get_flow_data(ticker)
    except NotImplementedError:
        return pd.DataFrame()


def get_earnings_history(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (quarterly_earnings, annual_earnings) DataFrames."""
    try:
        t = yf.Ticker(ticker)
        quarterly = t.quarterly_earnings if t.quarterly_earnings is not None else pd.DataFrame()
        annual    = t.earnings          if t.earnings is not None          else pd.DataFrame()
        return quarterly, annual
    except Exception as exc:
        logger.error("get_earnings_history(%s): %s", ticker, exc)
        return pd.DataFrame(), pd.DataFrame()


def get_financials(ticker: str) -> dict[str, pd.DataFrame]:
    """Return dict with income_stmt, balance_sheet, cash_flow (quarterly + annual)."""
    try:
        t = yf.Ticker(ticker)
        return {
            "income_annual":    _safe_df(t.income_stmt),
            "income_quarterly": _safe_df(t.quarterly_income_stmt),
            "balance_annual":   _safe_df(t.balance_sheet),
            "balance_quarterly":_safe_df(t.quarterly_balance_sheet),
            "cashflow_annual":  _safe_df(t.cashflow),
            "cashflow_quarterly":_safe_df(t.quarterly_cashflow),
        }
    except Exception as exc:
        logger.error("get_financials(%s): %s", ticker, exc)
        return {}


def get_peers(ticker: str, n: int = 5) -> list[str]:
    """
    Return a peer group for the given ticker.

    Currently uses a hardcoded sector map as a lightweight starting point.
    TODO: Replace with a proper peer-identification service (e.g. scrape
    Finviz peer group or use a paid data vendor).
    """
    _SECTOR_PEERS: dict[str, list[str]] = {
        "MRNA":  ["BNTX", "NVAX", "CVAC", "ARCT", "RBGX"],
        "REGN":  ["VRTX", "BIIB", "SGEN", "ALNY", "IONS"],
        "GILD":  ["ABBV", "BMY", "AMGN", "MRNA", "VRTX"],
        "VRTX":  ["REGN", "BIIB", "SGEN", "ALNY", "IONS"],
        "BIIB":  ["REGN", "VRTX", "IONS", "ALNY", "SAGE"],
        "AMGN":  ["GILD", "ABBV", "BMY", "BIIB", "REGN"],
        "0700.HK": ["9988.HK", "3690.HK", "1177.HK", "2269.HK", "6160.HK"],
        "2269.HK": ["6160.HK", "1801.HK", "1177.HK", "1093.HK", "3692.HK"],
        "6160.HK": ["2269.HK", "1801.HK", "1177.HK", "1093.HK", "3692.HK"],
    }
    t = ticker.upper()
    peers = _SECTOR_PEERS.get(t, [])
    if not peers:
        # Generic biotech fallback
        peers = ["MRNA", "REGN", "VRTX", "GILD", "AMGN"]
        if t in peers:
            peers = [p for p in peers if p != t][:n]
    return peers[:n]


def get_stock_data(ticker: str, period: str = "1y") -> dict:
    """
    Convenience bundle: fetch prices, company info and fundamentals in one call.
    Returns a dict with keys: prices, info, fundamentals, region.
    """
    adapter = get_adapter_for_ticker(ticker)
    start, end = period_to_dates(period)
    prices = get_price_history(ticker, period=period)
    info   = get_company_info(ticker)
    funds  = get_financial_metrics(ticker)
    return {
        "prices":      prices,
        "info":        info,
        "fundamentals": funds,
        "region":      adapter.get_region(),
        "ticker":      ticker,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_df(obj) -> pd.DataFrame:
    """Return obj if it's a non-None DataFrame, else empty DataFrame."""
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    return pd.DataFrame()
