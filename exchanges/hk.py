"""
Hong Kong Stock Exchange (HKEX) adapter.

Data sources:
- Prices / metadata / fundamentals : yfinance (.HK tickers)
- News                              : yfinance news feed
- Clinical trials                   : ClinicalTrials.gov (by company name)
- Filings                           : HKEXnews advanced search (HTML scraper)
- Flow data (CCASS)                 : CCASS shareholding search (HTML scraper)
"""
from __future__ import annotations

import logging
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from .base import BaseExchangeAdapter

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
_HKEX_SEARCH_URL = (
    "https://www.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main.aspx"
)
_CCASS_URL = "https://www.hkexnews.hk/sdw/search/searchsdw.aspx"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _aspnet_tokens(session: requests.Session, url: str) -> dict[str, str]:
    """GET a page and return its ASP.NET hidden form fields."""
    from bs4 import BeautifulSoup
    resp = session.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")
    tokens: dict[str, str] = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        el = soup.find("input", {"name": name})
        if el:
            tokens[name] = el.get("value", "")
    return tokens


def _parse_hk_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw[:10] if len(raw) >= 10 else None


def _numeric_code(ticker: str) -> str:
    """'6160.HK' → '6160' (no leading zeros, for HKEXnews form)."""
    t = ticker.upper().replace(".HK", "").lstrip("0")
    return t or "0"


def _padded_code(ticker: str) -> str:
    """'6160.HK' → '6160', '700.HK' → '0700' (4-digit padded, for CCASS form)."""
    t = ticker.upper().replace(".HK", "")
    try:
        return f"{int(t):04d}"
    except ValueError:
        return t


# ---------------------------------------------------------------------------
# HKEXnews filings scraper
# ---------------------------------------------------------------------------

def _fetch_hkex_filings(ticker: str, limit: int = 50) -> pd.DataFrame:
    """Scrape HKEXnews announcement search for the given HK ticker."""
    from bs4 import BeautifulSoup

    code = _numeric_code(ticker)
    session = requests.Session()
    empty = pd.DataFrame(columns=["date", "title", "type", "url"])

    try:
        tokens = _aspnet_tokens(session, _HKEX_SEARCH_URL)
    except Exception as exc:
        logger.error("hkex_filings tokens(%s): %s", code, exc)
        return empty

    form_data = {
        **tokens,
        "txtStockCode": code,
        "rbtnAllType": "rbtnAllType",
        "ddlDocTypePy": "AANNC",
        "txtDateFrom": "",
        "txtDateTo": "",
        "ddlTier": "0",
        "rdoHKEx": "rdoHKEx",
        "btnSearch": "Search",
    }

    try:
        resp = session.post(
            _HKEX_SEARCH_URL,
            data=form_data,
            headers={**_HEADERS, "Referer": _HKEX_SEARCH_URL},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("hkex_filings post(%s): %s", code, exc)
        return empty

    soup = BeautifulSoup(resp.content, "lxml")

    # Try multiple selectors — HKEX has updated their HTML over the years
    table = (
        soup.find("table", {"class": lambda c: c and "table-active-main" in c})
        or soup.find("table", {"id": "gvMain"})
    )
    if not table:
        result_div = soup.find("div", {"id": "pnlResult"})
        if result_div:
            table = result_div.find("table")
    if not table:
        # Last resort: first table with ≥ 3 columns
        for t in soup.find_all("table"):
            first_row = t.find("tr")
            if first_row and len(first_row.find_all(["th", "td"])) >= 3:
                table = t
                break

    rows = []
    if table:
        for tr in table.find_all("tr")[1 : limit + 1]:
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            link = tr.find("a")
            title = link.get_text(strip=True) if link else tds[1].get_text(strip=True)
            href = link.get("href", "") if link else ""
            if href and not href.startswith("http"):
                href = "https://www.hkexnews.hk" + href
            doc_type = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            date_raw = tds[-1].get_text(strip=True)
            rows.append({
                "date": _parse_hk_date(date_raw),
                "title": title,
                "type": doc_type,
                "url": href,
            })

    if not rows:
        logger.warning("hkex_filings: no rows parsed for %s", code)

    return pd.DataFrame(rows, columns=["date", "title", "type", "url"]) if rows else empty


# ---------------------------------------------------------------------------
# CCASS shareholding scraper
# ---------------------------------------------------------------------------

def _end_of_month_dates(months_back: int = 12) -> list[datetime]:
    today = datetime.utcnow()
    dates = []
    for m in range(1, months_back + 1):
        month = today.month - m
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = monthrange(year, month)[1]
        dates.append(datetime(year, month, last_day))
    return dates


def _fetch_ccass_snapshot(code_4d: str, date: datetime) -> pd.DataFrame:
    """Fetch one CCASS end-of-month snapshot. Creates its own session."""
    from bs4 import BeautifulSoup

    session = requests.Session()
    date_str = date.strftime("%Y-%m-%d")

    try:
        tokens = _aspnet_tokens(session, _CCASS_URL)
    except Exception as exc:
        logger.error("ccass tokens(%s %s): %s", code_4d, date_str, exc)
        return pd.DataFrame()

    form_data = {
        **tokens,
        "txtStockCode": code_4d,
        "ddlShareholdingDay": str(date.day),
        "ddlShareholdingMonth": f"{date.month:02d}",
        "ddlShareholdingYear": str(date.year),
        "btnSearch": "Search",
    }

    try:
        resp = session.post(
            _CCASS_URL,
            data=form_data,
            headers={**_HEADERS, "Referer": _CCASS_URL},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("ccass post(%s %s): %s", code_4d, date_str, exc)
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    table = (
        soup.find("table", {"id": "participantShareholdingList"})
        or soup.find("table", {"class": lambda c: c and "shareholding" in c.lower()})
    )
    if not table:
        result_div = soup.find("div", {"id": "pnlResultContent"}) or soup.find("div", {"id": "pnlResult"})
        if result_div:
            table = result_div.find("table")

    rows = []
    if table:
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            pid = tds[0].get_text(strip=True)
            if not pid or pid.lower() in ("total", "participant id"):
                continue
            name = tds[1].get_text(strip=True)
            shares_raw = tds[2].get_text(strip=True).replace(",", "")
            pct_raw = tds[3].get_text(strip=True).replace("%", "").strip()
            try:
                shares = int(shares_raw)
            except ValueError:
                continue
            try:
                pct = float(pct_raw)
            except ValueError:
                pct = None
            rows.append({
                "participant_id": pid,
                "participant_name": name,
                "shares": shares,
                "percentage": pct,
                "snapshot_date": date_str,
            })

    if not rows:
        logger.debug("ccass: no rows for %s on %s", code_4d, date_str)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _fetch_ccass_flow(ticker: str, months_back: int = 12) -> pd.DataFrame:
    """Fetch end-of-month CCASS snapshots for the past N months (parallel)."""
    code_4d = _padded_code(ticker)
    dates = _end_of_month_dates(months_back)
    empty = pd.DataFrame(
        columns=["participant_id", "participant_name", "shares", "percentage", "snapshot_date"]
    )

    dfs: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_ccass_snapshot, code_4d, d): d for d in dates}
        for fut in as_completed(futures):
            try:
                df = fut.result()
                if not df.empty:
                    dfs.append(df)
            except Exception as exc:
                logger.error("ccass future(%s): %s", code_4d, exc)

    if not dfs:
        return empty
    return pd.concat(dfs, ignore_index=True).sort_values("snapshot_date", ascending=False)


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class HKExchangeAdapter(BaseExchangeAdapter):
    """Adapter for HKEX-listed equities."""

    def get_region(self) -> str:
        return "HK"

    def _normalize_ticker(self, ticker: str) -> str:
        """Normalise to 4-digit HKEX format: '700' → '0700.HK'."""
        t = ticker.strip().upper()
        if t.endswith(".HK"):
            numeric = t[:-3].lstrip("0") or "0"
            return f"{int(numeric):04d}.HK"
        if t.isdigit():
            return f"{int(t):04d}.HK"
        return t

    def get_metadata(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_metadata
        return fetch_yfinance_metadata(self._normalize_ticker(ticker))

    def get_fundamentals(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_fundamentals
        return fetch_yfinance_fundamentals(self._normalize_ticker(ticker))

    def get_prices(self, ticker: str, start_date: datetime, end_date: datetime, interval: str = "1d") -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_prices
        return fetch_yfinance_prices(self._normalize_ticker(ticker), start_date, end_date, interval)

    def get_trials(self, ticker: str) -> pd.DataFrame:
        from data_fetcher import fetch_clinicaltrials
        return fetch_clinicaltrials(self._normalize_ticker(ticker))

    def get_filings(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        return _fetch_hkex_filings(self._normalize_ticker(ticker), limit)

    def get_news(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_news
        return fetch_yfinance_news(self._normalize_ticker(ticker), limit)

    def get_flow_data(self, ticker: str) -> pd.DataFrame:
        return _fetch_ccass_flow(self._normalize_ticker(ticker))
