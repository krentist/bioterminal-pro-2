"""
Hong Kong Stock Exchange (HKEX) adapter.

Current state
-------------
- Prices / metadata / fundamentals : yfinance (.HK tickers)
- News                              : yfinance news feed
- Filings                           : STUB — empty DataFrame + TODO plan
- Flow data (CCASS)                 : STUB — empty DataFrame + TODO plan
- Clinical trials                   : STUB — empty DataFrame + TODO plan

Future CCASS scraper plan
--------------------------
Target : https://www.hkexnews.hk/sdw/search/searchsdw.aspx
Method : HTTP POST with form fields:
    txtStockCode  = "0700"
    ddlShareholdingDay / Month / Year = target date components
    btnSearch     = "Search"
Parse the returned HTML table (participant_id, name, shares, %) using
BeautifulSoup or lxml.  Fetch end-of-month snapshots for the last 12 months.

fetch_ccass_snapshot(hk_code: str, date: datetime) -> pd.DataFrame
    Columns: participant_id, participant_name, shares, percentage, snapshot_date

Future HKEXnews filings scraper plan
--------------------------------------
Target : https://www.hkexnews.hk/listedco/listconews/advancedsearch/
Method : POST form with stock code; parse announcement list.

fetch_hkex_filings(hk_code: str, limit: int = 50) -> pd.DataFrame
    Columns: date, title, type, url
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .base import BaseExchangeAdapter


class HKExchangeAdapter(BaseExchangeAdapter):
    """Adapter for HKEX-listed equities."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def get_region(self) -> str:
        return "HK"

    # ------------------------------------------------------------------
    # Ticker normalisation
    # ------------------------------------------------------------------

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Ensure ticker is in the yfinance HKEX format: "0700.HK".

        Accepts bare numeric codes ("700", "0700") or already-formatted
        strings ("0700.HK").  Pads to 4 digits as HKEX convention requires.
        """
        t = ticker.strip().upper()
        if t.endswith(".HK"):
            numeric = t[:-3].lstrip("0") or "0"
            return f"{int(numeric):04d}.HK"
        if t.isdigit():
            return f"{int(t):04d}.HK"
        return t  # pass through non-numeric suffixed tickers unchanged

    # ------------------------------------------------------------------
    # Company info
    # ------------------------------------------------------------------

    def get_metadata(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_metadata
        return fetch_yfinance_metadata(self._normalize_ticker(ticker))

    def get_fundamentals(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_fundamentals
        return fetch_yfinance_fundamentals(self._normalize_ticker(ticker))

    # ------------------------------------------------------------------
    # Price data
    # ------------------------------------------------------------------

    def get_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_prices
        return fetch_yfinance_prices(
            self._normalize_ticker(ticker), start_date, end_date, interval
        )

    # ------------------------------------------------------------------
    # Filings  (STUB)
    # ------------------------------------------------------------------

    def get_filings(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        """
        TODO: Implement fetch_hkex_filings() scraper.

        Scrape HKEXnews announcement search for the given stock code.
        Return DataFrame with columns: date, title, type, url
        """
        return pd.DataFrame(columns=["date", "title", "type", "url"])

    # ------------------------------------------------------------------
    # Clinical trials  (STUB)
    # ------------------------------------------------------------------

    def get_trials(self, ticker: str) -> pd.DataFrame:
        """
        TODO: Many HKEX biotech companies (BeiGene, WuXi, CSPC, Innovent,
        Hansoh, etc.) register trials on ClinicalTrials.gov under their
        English company name.

        Plan: resolve ticker → company name via get_metadata(), then call
        fetch_clinicaltrials_by_sponsor(company_name) from data_fetcher.
        """
        return pd.DataFrame(
            columns=[
                "nct_id", "title", "phase", "status", "condition",
                "start_date", "primary_completion_date", "enrollment", "sponsor",
            ]
        )

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_news
        return fetch_yfinance_news(self._normalize_ticker(ticker), limit)

    # ------------------------------------------------------------------
    # CCASS flow data  (STUB)
    # ------------------------------------------------------------------

    def get_flow_data(self, ticker: str) -> pd.DataFrame:
        """
        TODO: Implement CCASS shareholding snapshot scraper.

        URL  : https://www.hkexnews.hk/sdw/search/searchsdw.aspx
        POST : txtStockCode, ddlShareholdingDay/Month/Year, btnSearch=Search
        Parse: HTML table → participant_id, name, shares, percentage

        Fetch end-of-month for last 12 months; concatenate into long-format DF.

        Return schema:
            participant_id, participant_name, shares, percentage, snapshot_date
        """
        return pd.DataFrame(
            columns=[
                "participant_id", "participant_name",
                "shares", "percentage", "snapshot_date",
            ]
        )
