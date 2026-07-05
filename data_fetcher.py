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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
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

_INFO_CACHE: dict[str, object] = {}
_INFO_CACHE_LOCK = Lock()
_INFO_CACHE_TTL = 60  # seconds
_INFO_LOADING = object()  # sentinel for thundering-herd guard


def normalize_ticker(ticker: str) -> str:
    """Canonicalise a raw ticker via its exchange adapter.

    Bare HK codes ('700', '6160') are padded to '0700.HK' / '6160.HK'; US
    tickers pass through unchanged. Idempotent, so applying it to an already
    normalised ticker is a no-op. Lets every server route accept bare codes
    without each having to know the exchange rules.
    """
    try:
        from exchanges import get_exchange_adapter
        adapter = get_exchange_adapter(ticker)
        norm = getattr(adapter, "_normalize_ticker", None)
        return norm(ticker) if norm else ticker
    except Exception:
        return ticker


def _cached_yf_info(ticker: str) -> dict:
    """Fetch yfinance .info with a 60-second TTL cache.

    Uses a sentinel (_INFO_LOADING) so that only one thread fetches from
    yfinance per ticker; concurrent threads return {} immediately rather
    than all hammering the upstream API in parallel.
    """
    ticker = normalize_ticker(ticker)
    now = time.monotonic()
    with _INFO_CACHE_LOCK:
        entry = _INFO_CACHE.get(ticker)
        if entry is _INFO_LOADING:
            return {}
        if entry is not None:
            value, ts = entry  # type: ignore[misc]
            if now - ts < _INFO_CACHE_TTL:
                return value
        _INFO_CACHE[ticker] = _INFO_LOADING  # claim slot

    info = yf.Ticker(ticker).info or {}

    with _INFO_CACHE_LOCK:
        _INFO_CACHE[ticker] = (info, time.monotonic())
    return info


# ---------------------------------------------------------------------------
# Cash-flow statement cache (for cash-burn / runway)
# ---------------------------------------------------------------------------

_CASHFLOW_CACHE: dict[str, tuple[dict, float]] = {}
_CASHFLOW_CACHE_LOCK = Lock()
_CASHFLOW_CACHE_TTL = 600  # 10 minutes


def get_annual_cashflow(ticker: str) -> dict:
    """Latest annual Free Cash Flow / Operating Cash Flow from the cash-flow statement.

    The yfinance ``.info`` ``freeCashflow`` scalar is unreliable (it can be a single
    stray quarter — e.g. it reports Moderna at −$20M when the real annual burn is
    ~−$2B), so the reported statement figure is the trustworthy source for runway.
    Cached for 10 minutes. Returns {"free_cash_flow": float|None, "operating_cash_flow": float|None}.
    """
    ticker = normalize_ticker(ticker)
    now = time.monotonic()
    with _CASHFLOW_CACHE_LOCK:
        entry = _CASHFLOW_CACHE.get(ticker)
        if entry is not None:
            val, ts = entry
            if now - ts < _CASHFLOW_CACHE_TTL:
                return val

    result = {"free_cash_flow": None, "operating_cash_flow": None}
    try:
        cf = yf.Ticker(ticker).cashflow
        if cf is not None and not cf.empty:
            for key, dst in (("Free Cash Flow", "free_cash_flow"),
                             ("Operating Cash Flow", "operating_cash_flow")):
                if key in cf.index:
                    vals = cf.loc[key].dropna()
                    if len(vals):
                        result[dst] = float(vals.iloc[0])
    except Exception as exc:
        logger.debug("get_annual_cashflow(%s): %s", ticker, exc)

    with _CASHFLOW_CACHE_LOCK:
        _CASHFLOW_CACHE[ticker] = (result, time.monotonic())
    return result


# ---------------------------------------------------------------------------
# Ownership & short interest cache
# ---------------------------------------------------------------------------

_OWNERSHIP_CACHE: dict[str, tuple[dict, float]] = {}
_OWNERSHIP_CACHE_LOCK = Lock()
_OWNERSHIP_CACHE_TTL = 600  # 10 minutes


def get_ownership(ticker: str) -> dict:
    """Institutional/insider ownership, short interest, and top institutional holders.

    Sourced from yfinance .info plus the institutional_holders table. Short-interest
    fields are US-reported (None for most HK/other listings, which is handled by the
    UI). Cached for 10 minutes.
    """
    ticker = normalize_ticker(ticker)
    now = time.monotonic()
    with _OWNERSHIP_CACHE_LOCK:
        entry = _OWNERSHIP_CACHE.get(ticker)
        if entry is not None:
            val, ts = entry
            if now - ts < _OWNERSHIP_CACHE_TTL:
                return val

    info = _cached_yf_info(ticker)

    shares_short = info.get("sharesShort")
    prior_short  = info.get("sharesShortPriorMonth")
    si_change = None
    try:
        if shares_short and prior_short:
            si_change = shares_short / prior_short - 1
    except (TypeError, ZeroDivisionError):
        si_change = None

    date_si = info.get("dateShortInterest")
    if isinstance(date_si, (int, float)):
        try:
            date_si = datetime.fromtimestamp(date_si, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OverflowError, OSError):
            date_si = None

    top: list[dict] = []
    try:
        ih = yf.Ticker(ticker).institutional_holders
        if ih is not None and not ih.empty:
            for _, r in ih.head(10).iterrows():
                dr = r.get("Date Reported")
                top.append({
                    "holder":       str(r.get("Holder", "")),
                    "pctHeld":      float(r["pctHeld"])   if pd.notna(r.get("pctHeld"))   else None,
                    "shares":       int(r["Shares"])      if pd.notna(r.get("Shares"))    else None,
                    "value":        float(r["Value"])     if pd.notna(r.get("Value"))     else None,
                    "pctChange":    float(r["pctChange"]) if pd.notna(r.get("pctChange")) else None,
                    "dateReported": str(dr.date()) if hasattr(dr, "date") else (str(dr) if dr is not None else None),
                })
    except Exception as exc:
        logger.debug("get_ownership holders(%s): %s", ticker, exc)

    insider_txns: list[dict] = []
    try:
        it = yf.Ticker(ticker).insider_transactions
        if it is not None and not it.empty:
            for _, r in it.head(15).iterrows():
                d = r.get("Start Date")
                insider_txns.append({
                    "date":        str(d.date()) if hasattr(d, "date") else (str(d) if d is not None else None),
                    "insider":     str(r.get("Insider", "")) or None,
                    "position":    str(r.get("Position", "")) or None,
                    "transaction": str(r.get("Transaction", "")) or None,
                    "shares":      int(r["Shares"]) if pd.notna(r.get("Shares")) else None,
                    "value":       float(r["Value"]) if pd.notna(r.get("Value")) else None,
                })
    except Exception as exc:
        logger.debug("get_ownership insider(%s): %s", ticker, exc)

    result = {
        "heldPctInstitutions":    info.get("heldPercentInstitutions"),
        "heldPctInsiders":        info.get("heldPercentInsiders"),
        "shortPctOfFloat":        info.get("shortPercentOfFloat"),
        "sharesShort":            shares_short,
        "sharesShortPriorMonth":  prior_short,
        "shortInterestChangePct": si_change,
        "daysToCover":            info.get("shortRatio"),
        "dateShortInterest":      date_si,
        "floatShares":            info.get("floatShares"),
        "sharesOutstanding":      info.get("sharesOutstanding"),
        "topInstitutions":        top,
        "insiderTransactions":    insider_txns,
        "source":                 "Yahoo Finance",
        "retrievedAt":            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with _OWNERSHIP_CACHE_LOCK:
        _OWNERSHIP_CACHE[ticker] = (result, time.monotonic())
    return result


# ClinicalTrials.gov REST API v2
_CT_BASE = "https://clinicaltrials.gov/api/v2/studies"
_CT_FIELDS = (
    "NCTId,BriefTitle,OverallStatus,Phase,Condition,"
    "LeadSponsorName,StartDate,PrimaryCompletionDate,EnrollmentCount,"
    "EnrollmentType,PrimaryOutcomeMeasure,InterventionName,InterventionType,"
    "ArmGroupLabel,ArmGroupType,DesignPrimaryPurpose"
)

# Arm-group types that denote a control/comparator arm (vs. an experimental arm).
_COMPARATOR_ARM_TYPES = {"ACTIVE_COMPARATOR", "PLACEBO_COMPARATOR", "SHAM_COMPARATOR", "NO_INTERVENTION"}

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
    ticker = normalize_ticker(ticker)
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
    ticker = normalize_ticker(ticker)
    news = []
    try:
        t = yf.Ticker(ticker)
        # Prefer get_news(tab="all"): it includes press releases, where biotech news lives,
        # and surfaces items the bare .news property misses entirely for some tickers
        # (e.g. HK biotechs like 6628.HK, where .news returns [] but tab="all" returns the
        # company's real releases). Fall back to .news for older yfinance / empty results.
        try:
            news = t.get_news(count=limit, tab="all") or []
        except (AttributeError, TypeError):
            news = []
        if not news:
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

    Ticker-specific overrides (_CT_TICKER_NAME_OVERRIDES) take precedence so that
    known rebrands or Chinese companies whose CT.gov registration differs from the
    yfinance display name are always found.
    """
    try:
        ticker = normalize_ticker(ticker)
        meta = fetch_yfinance_metadata(ticker)
        company_name = meta.get("name") or ticker
        variants = _ct_name_variants(company_name)

        # Prepend override names so they're searched first; merge without duplicates
        overrides = _CT_TICKER_NAME_OVERRIDES.get(ticker.upper(), [])
        merged: list[str] = []
        for name in overrides + variants:
            if name and name not in merged:
                merged.append(name)

        return fetch_clinicaltrials_multi(merged[:6])  # cap at 6 to avoid rate-limiting
    except Exception as exc:
        logger.error("fetch_clinicaltrials(%s): %s", ticker, exc)
        return _empty_trials_df()


# Known HK/Chinese ticker → primary CT.gov sponsor name overrides.
# Used when the yfinance company name diverges from CT.gov registration
# (e.g. rebrands, English-name differences, Chinese parent vs. trial sponsor).
_CT_TICKER_NAME_OVERRIDES: dict[str, list[str]] = {
    "6160.HK": ["BeiGene", "BeOne Medicines"],   # rebranded 2024
    "2269.HK": ["WuXi Biologics"],
    "1801.HK": ["Innovent Biologics"],
    "3692.HK": ["Hansoh Pharmaceutical"],
    "1093.HK": ["CSPC Pharmaceutical"],
    "1177.HK": ["Sino Biopharmaceutical", "Sino Biopharm"],
    "9688.HK": ["Zai Lab"],
    "9987.HK": ["Legend Biotech"],
    "9995.HK": ["RemeGen"],
    "2196.HK": ["Shanghai Fosun Pharmaceutical", "Fosun Pharma"],
    "2359.HK": ["WuXi AppTec"],
}


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
        arms_mod = ps.get("armsInterventionsModule", {})
        out_mod  = ps.get("outcomesModule", {})

        phases    = design.get("phases", [])
        phase_str = ", ".join(p.replace("PHASE", "Phase ") for p in phases) if phases else "N/A"

        enroll_info = design.get("enrollmentInfo", {})
        interventions = [i.get("name") for i in arms_mod.get("interventions", []) if i.get("name")]
        comparator_arms = [
            a.get("label") for a in arms_mod.get("armGroups", [])
            if str(a.get("type", "")).upper() in _COMPARATOR_ARM_TYPES and a.get("label")
        ]
        primary_endpoints = [
            o.get("measure") for o in out_mod.get("primaryOutcomes", []) if o.get("measure")
        ]

        rows.append({
            "nct_id":                  id_mod.get("nctId"),
            "title":                   id_mod.get("briefTitle"),
            "phase":                   phase_str,
            "status":                  stat_mod.get("overallStatus"),
            "condition":               ", ".join(cond_mod.get("conditions", [])),
            "start_date":              _ct_date(stat_mod.get("startDateStruct")),
            "primary_completion_date": _ct_date(stat_mod.get("primaryCompletionDateStruct")),
            "enrollment":              enroll_info.get("count"),
            "enrollment_type":         enroll_info.get("type"),        # ACTUAL vs ESTIMATED
            "sponsor":                 spon_mod.get("leadSponsor", {}).get("name"),
            "primary_endpoint":        "; ".join(primary_endpoints[:2]) or None,
            "interventions":           ", ".join(interventions[:6]) or None,
            "comparator":              ", ".join(comparator_arms[:4]) or None,
            "primary_purpose":         design.get("designInfo", {}).get("primaryPurpose"),
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
            "start_date", "primary_completion_date", "enrollment", "enrollment_type",
            "sponsor", "primary_endpoint", "interventions", "comparator", "primary_purpose",
        ]
    )


def fetch_clinicaltrials_by_condition(condition: str, page_size: int = 60) -> pd.DataFrame:
    """Search interventional trials by indication/condition (for competitive landscape)."""
    if not (condition or "").strip():
        return _empty_trials_df()
    rows = _ct_search_raw(condition.strip(), "query.cond", page_size)
    return pd.DataFrame(rows) if rows else _empty_trials_df()


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


# Curated peer sets. These are hand-picked comparable sets, not an exhaustive
# screen — the UI is explicit that peers are a curated group.
_SECTOR_PEERS: dict[str, list[str]] = {
    "MRNA":  ["BNTX", "NVAX", "VRTX", "REGN", "GILD"],
    "REGN":  ["VRTX", "BIIB", "ALNY", "IONS", "AMGN"],
    "GILD":  ["ABBV", "BMY", "AMGN", "MRNA", "VRTX"],
    "VRTX":  ["REGN", "BIIB", "ALNY", "IONS", "BMRN"],
    "BIIB":  ["REGN", "VRTX", "IONS", "ALNY", "SAGE"],
    "AMGN":  ["GILD", "ABBV", "BMY", "BIIB", "REGN"],
    "0700.HK": ["9988.HK", "3690.HK", "1810.HK", "9999.HK", "0981.HK"],
    "2269.HK": ["6160.HK", "1801.HK", "1177.HK", "1093.HK", "3692.HK"],
    "6160.HK": ["2269.HK", "1801.HK", "1177.HK", "9688.HK", "9995.HK"],
}

_US_BIOTECH_PEERS = [
    "MRNA", "BNTX", "REGN", "VRTX", "GILD", "AMGN", "BIIB",
    "ALNY", "IONS", "INCY", "EXEL", "NBIX", "SRPT", "BMRN", "RARE",
]
_HK_BIOTECH_PEERS = [
    "6160.HK", "2269.HK", "1801.HK", "3692.HK", "1093.HK",
    "1177.HK", "9688.HK", "9995.HK", "6963.HK", "2196.HK",
]


def get_peers(ticker: str, n: int = 5) -> list[str]:
    """
    Return a curated peer group for the given ticker.

    Explicit per-ticker overrides take precedence; otherwise falls back to the
    region's biotech peer set (HK vs US), excluding the ticker itself. This is a
    curated comparable set, not an exhaustive sector screen.
    """
    t = normalize_ticker(ticker).upper()
    peers = list(_SECTOR_PEERS.get(t, []))
    if not peers:
        pool = _HK_BIOTECH_PEERS if t.endswith(".HK") else _US_BIOTECH_PEERS
        peers = [p for p in pool if p.upper() != t]
    peers = [p for p in peers if p.upper() != t]
    return peers[:n]


# ---------------------------------------------------------------------------
# Peer comparables table
# ---------------------------------------------------------------------------

_PEERS_CACHE: dict[str, tuple[list, float]] = {}
_PEERS_CACHE_LOCK = Lock()
_PEERS_CACHE_TTL = 600  # 10 minutes


def _peer_row(ticker: str, is_subject: bool) -> Optional[dict]:
    try:
        info = _cached_yf_info(ticker)
    except Exception:
        return None
    if not info:
        return None
    price  = info.get("regularMarketPrice") or info.get("currentPrice")
    target = info.get("targetMeanPrice")
    upside = None
    try:
        if target and price:
            upside = target / price - 1
    except (TypeError, ZeroDivisionError):
        upside = None
    return {
        "ticker":        ticker.upper(),
        "name":          info.get("shortName") or info.get("longName") or ticker,
        "marketCap":     info.get("marketCap"),
        "price":         price,
        "currency":      info.get("currency", "USD"),
        "evToRevenue":   info.get("enterpriseToRevenue"),
        "psRatio":       info.get("priceToSalesTrailing12Months"),
        "revenueGrowth": info.get("revenueGrowth"),
        "grossMargin":   info.get("grossMargins"),
        "profitMargin":  info.get("profitMargins"),
        "cash":          info.get("totalCash"),
        "targetUpside":  upside,
        "isSubject":     is_subject,
    }


def get_peer_comps(ticker: str, n: int = 5) -> list[dict]:
    """Comparable-metrics table for a ticker and its curated peers (subject first).

    Uses only fast .info fields, fetched in parallel, cached 10 minutes.
    """
    subject = normalize_ticker(ticker).upper()
    now = time.monotonic()
    with _PEERS_CACHE_LOCK:
        entry = _PEERS_CACHE.get(subject)
        if entry is not None:
            val, ts = entry
            if now - ts < _PEERS_CACHE_TTL:
                return val

    ordered: list[str] = []
    seen: set[str] = set()
    for x in [subject] + get_peers(subject, n):
        u = x.upper()
        if u not in seen:
            seen.add(u)
            ordered.append(x)

    rows: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(_peer_row, x, x.upper() == subject): x for x in ordered}
        for fut in as_completed(futs):
            try:
                r = fut.result()
                if r:
                    rows[r["ticker"]] = r
            except Exception:
                pass

    # Subject first, then peers by descending market cap.
    subject_row = rows.pop(subject, None)
    peer_rows = sorted(rows.values(), key=lambda r: r.get("marketCap") or 0, reverse=True)
    result = ([subject_row] if subject_row else []) + peer_rows

    with _PEERS_CACHE_LOCK:
        _PEERS_CACHE[subject] = (result, time.monotonic())
    return result


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
