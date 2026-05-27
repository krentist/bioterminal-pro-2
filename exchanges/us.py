"""
US exchange adapter.

Data sources
------------
- Prices, metadata, fundamentals : yfinance
- Clinical trials                 : ClinicalTrials.gov REST API v2
- News                            : yfinance news feed
- Filings                         : yfinance news (proxy until SEC EDGAR wired up)
- Institutional flow              : stub (TODO: SEC EDGAR form-13F API)

All calls into data_fetcher are lazy (inside method bodies) to avoid the
circular-import that would occur if data_fetcher imported from exchanges at
module scope while us.py imported from data_fetcher at module scope.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .base import BaseExchangeAdapter


class USExchangeAdapter(BaseExchangeAdapter):
    """Adapter for US-listed equities (NYSE, NASDAQ, OTC)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def get_region(self) -> str:
        return "US"

    # ------------------------------------------------------------------
    # Company info
    # ------------------------------------------------------------------

    def get_metadata(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_metadata
        return fetch_yfinance_metadata(ticker)

    def get_fundamentals(self, ticker: str) -> dict:
        from data_fetcher import fetch_yfinance_fundamentals
        return fetch_yfinance_fundamentals(ticker)

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
        return fetch_yfinance_prices(ticker, start_date, end_date, interval)

    # ------------------------------------------------------------------
    # Regulatory filings
    # ------------------------------------------------------------------

    def get_filings(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        """
        Returns recent news as a lightweight filing proxy.

        TODO: Replace with full SEC EDGAR full-text search API:
              GET https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22
              &dateRange=custom&startdt=...&enddt=...&forms=8-K,10-K,10-Q
              Columns to return: date, title, type (form type), url
        """
        from data_fetcher import fetch_yfinance_news
        df = fetch_yfinance_news(ticker, limit)
        # Rename to match the filings schema so callers use one column set
        df = df.rename(columns={"summary": "type"}) if "summary" in df.columns else df
        return df

    # ------------------------------------------------------------------
    # Clinical trials (biotech-specific)
    # ------------------------------------------------------------------

    def get_trials(self, ticker: str) -> pd.DataFrame:
        from data_fetcher import fetch_clinicaltrials
        return fetch_clinicaltrials(ticker)

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_news
        return fetch_yfinance_news(ticker, limit)

    # ------------------------------------------------------------------
    # Institutional flow (13F stub)
    # ------------------------------------------------------------------

    def get_flow_data(self, ticker: str) -> pd.DataFrame:
        """
        TODO: Implement via SEC EDGAR form-13F API.

        Plan:
            1. Resolve ticker → CIK via
               https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=...
            2. Fetch 13F-HR filings from
               https://data.sec.gov/submissions/CIK{cik:010d}.json
            3. Parse holdings table from each filing XML.

        Return schema:
            filer, filer_cik, shares, value_usd, quarter, pct_of_float,
            change_shares, change_type (new / increased / decreased / sold)
        """
        return pd.DataFrame(
            columns=[
                "filer", "filer_cik", "shares", "value_usd",
                "quarter", "pct_of_float", "change_shares", "change_type",
            ]
        )
