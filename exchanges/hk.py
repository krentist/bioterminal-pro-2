"""
Hong Kong Stock Exchange (HKEX) adapter.

Data sources:
- Prices / metadata / fundamentals : yfinance (.HK tickers)
- News                              : yfinance news feed
- Clinical trials                   : ClinicalTrials.gov (by company name)
- Filings                           : HKEXnews titleSearchServlet REST API
- Flow data (CCASS)                 : CCASS shareholding search (www3, form POST)
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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

# CCASS moved to www3 subdomain (www returns blank SPA response)
_CCASS_URL = "https://www3.hkexnews.hk/sdw/search/searchsdw.aspx"

# HKEXnews REST API (replaces the old ASP.NET form which is now a SPA)
_HKEX_API_BASE = "https://www1.hkexnews.hk"
_HKEX_SEARCH_SERVLET = _HKEX_API_BASE + "/search/titleSearchServlet.do"
_HKEX_STOCKS_JSON_URL = _HKEX_API_BASE + "/ncms/script/eds/activestock_sehk_e.json"

# In-memory stock code → internal stockId cache (populated on first filing request)
_HKEX_STOCK_ID_CACHE: dict[str, int] = {}  # "06160" → 194142


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_hk_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw[:10] if len(raw) >= 10 else None


def _ccass_code(ticker: str) -> str:
    """'6160.HK' → '06160' (5-digit zero-padded, required by CCASS form)."""
    t = ticker.upper().replace(".HK", "")
    try:
        return f"{int(t):05d}"
    except ValueError:
        return t


# ---------------------------------------------------------------------------
# HKEXnews filings — REST API via titleSearchServlet.do
# ---------------------------------------------------------------------------

def _load_hkex_stock_ids() -> None:
    """Populate _HKEX_STOCK_ID_CACHE from the active-stocks JSON if empty.

    Retries up to 3 times with exponential back-off — the www1 endpoint can be
    slow from outside HK, and a single timeout would otherwise leave every
    subsequent filings request returning empty for the lifetime of the process.
    """
    global _HKEX_STOCK_ID_CACHE
    if _HKEX_STOCK_ID_CACHE:
        return
    for attempt in range(3):
        try:
            r = requests.get(_HKEX_STOCKS_JSON_URL, headers=_HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            _HKEX_STOCK_ID_CACHE = {item["c"]: item["i"] for item in data if item.get("c") and item.get("i")}
            return
        except Exception as exc:
            logger.warning("hkex_stock_ids attempt %d/3: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    logger.error("hkex_stock_ids: all retries exhausted — filings will be unavailable")


def _fetch_hkex_filings(ticker: str, limit: int = 50) -> pd.DataFrame:
    """
    Fetch HKEXnews announcements via the titleSearchServlet.do REST API.

    The old ASP.NET advanced-search form migrated to a JS SPA; the REST API
    it calls internally is stable and returns JSON directly.
    """
    code_5d = _ccass_code(ticker)
    empty = pd.DataFrame(columns=["date", "title", "type", "url"])

    _load_hkex_stock_ids()
    stock_id = _HKEX_STOCK_ID_CACHE.get(code_5d)
    if stock_id is None:
        logger.warning("hkex_filings: no stockId for %s (code=%s)", ticker, code_5d)
        return empty

    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": str(stock_id),
        "documentType": "-1",
        "fromDate": "",
        "toDate": "",
        "title": "",
        "searchType": "rbAfter2006",
        "t1code": "-2",
        "t2Gcode": "-2",
        "t2code": "-2",
        "rowRange": str(limit),
        "lang": "E",
    }

    try:
        resp = requests.get(
            _HKEX_SEARCH_SERVLET,
            params=params,
            headers={
                **_HEADERS,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": _HKEX_API_BASE + "/search/titlesearch.xhtml",
            },
            timeout=15,
        )
        resp.raise_for_status()
        envelope = resp.json()
    except Exception as exc:
        logger.error("hkex_filings(%s): %s", ticker, exc)
        return empty

    try:
        items = json.loads(envelope.get("result", "[]"))
    except Exception:
        return empty

    rows = []
    for item in items[:limit]:
        date_str = _parse_hk_date(item.get("DATE_TIME", ""))
        title = html.unescape(item.get("TITLE", "")).strip()
        if not title:
            continue
        # SHORT_TEXT: "Announcements and Notices - [Type]<br/> ... More" → extract "Type".
        # Strip tags, decode HTML entities (&#x2f; → /), drop the CT.gov "...More"
        # expander tail, collapse whitespace, and cap length so the field stays a label.
        short_text = html.unescape(re.sub(r"<[^>]+>", " ", item.get("SHORT_TEXT", "")))
        short_text = re.split(r"\.\.\.\s*More\b", short_text)[0]
        short_text = re.sub(r"\s+", " ", short_text).strip()
        filing_type = short_text.split(" - ", 1)[-1] if " - " in short_text else short_text
        filing_type = filing_type.strip(" []").strip()
        if len(filing_type) > 80:
            filing_type = filing_type[:79].rstrip() + "…"
        file_link = item.get("FILE_LINK", "")
        url = (_HKEX_API_BASE + file_link) if file_link else ""
        rows.append({"date": date_str, "title": title, "type": filing_type, "url": url})

    return pd.DataFrame(rows, columns=["date", "title", "type", "url"]) if rows else empty


# ---------------------------------------------------------------------------
# CCASS shareholding scraper
# ---------------------------------------------------------------------------

def _end_of_month_dates(months_back: int = 12) -> list[datetime]:
    """Return end-of-month dates for the past N complete months.

    CCASS publishes shareholding data with a 1-2 business day lag.  If today
    is within the first 3 days of a new month the previous month-end may not
    be available yet, so we start from 2 months ago to avoid timeout-waiting
    for unpublished data.
    """
    today = datetime.now(timezone.utc)
    start_offset = 2 if today.day <= 3 else 1
    dates = []
    for m in range(start_offset, months_back + start_offset):
        month = today.month - m
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = monthrange(year, month)[1]
        dates.append(datetime(year, month, last_day))
    return dates



def _fetch_ccass_flow(ticker: str, months_back: int = 12) -> pd.DataFrame:
    """
    Fetch end-of-month CCASS snapshots for the past N months (default 12).

    HKEX ignores __VIEWSTATE validation, so we POST directly with a stable
    __VIEWSTATEGENERATOR. Requests are parallelised (max 4 workers) to bring
    12-month fetch time from ~24s down to ~8s.
    """
    from bs4 import BeautifulSoup

    code_5d = _ccass_code(ticker)
    dates = _end_of_month_dates(months_back)
    empty = pd.DataFrame(
        columns=["participant_id", "participant_name", "shares", "percentage", "snapshot_date"]
    )

    base_form = {
        "__EVENTTARGET": "btnSearch",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": "",
        "__VIEWSTATEGENERATOR": "A7B2BBE2",
        "today": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "sortBy": "shareholding",
        "sortDirection": "desc",
        "originalShareholdingDate": "",
        "alertMsg": "",
        "txtStockName": "",
        "txtParticipantID": "",
        "txtParticipantName": "",
        "txtSelPartID": "",
    }

    def _fetch_one(date: datetime) -> pd.DataFrame:
        form_data = {
            **base_form,
            "txtShareholdingDate": date.strftime("%Y/%m/%d"),
            "txtStockCode": code_5d,
        }
        date_str = date.strftime("%Y-%m-%d")
        resp = None
        for attempt in range(2):
            try:
                resp = requests.post(
                    _CCASS_URL,
                    data=form_data,
                    headers={**_HEADERS, "Referer": _CCASS_URL},
                    timeout=25,
                )
                resp.raise_for_status()
                break
            except Exception as exc:
                logger.warning("ccass POST(%s %s) attempt %d/2: %s", code_5d, date_str, attempt + 1, exc)
                if attempt == 0:
                    time.sleep(1)
        if resp is None or not resp.ok:
            return pd.DataFrame()

        soup = BeautifulSoup(resp.content, "lxml")
        tbl = soup.find(
            "table",
            {"class": lambda c: c and "table-scroll" in (c if isinstance(c, str) else " ".join(c))},
        )
        if not tbl:
            return pd.DataFrame()

        def _body(td) -> str:
            div = td.find("div", class_="mobile-list-body")
            return div.get_text(strip=True) if div else td.get_text(strip=True)

        rows = []
        for tr in tbl.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            pid = _body(tds[0])
            if not pid or pid.lower() == "participant id":
                continue
            name = _body(tds[1])
            shares_raw = _body(tds[3]).replace(",", "")
            pct_raw = _body(tds[4]).replace("%", "").strip()
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
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    dfs: list[pd.DataFrame] = []
    # Max 3 workers — HKEX servers are sensitive to rapid concurrent POSTs from
    # outside HK; 3 keeps fetch time reasonable without triggering rate-limits.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_one, d): d for d in dates}
        for fut in as_completed(futures):
            try:
                df = fut.result()
                if not df.empty:
                    dfs.append(df)
            except Exception as exc:
                logger.error("ccass flow(%s): %s", code_5d, exc)

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
