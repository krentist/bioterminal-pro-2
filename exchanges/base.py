"""
Abstract base class for exchange/region-specific data adapters.

Each concrete subclass encapsulates all data-source logic for one exchange,
exposing a uniform interface to the rest of the application.

Method contract
---------------
- Required (abstractmethod): get_region, get_metadata, get_prices, get_fundamentals
- Optional (raise NotImplementedError by default): get_filings, get_trials,
  get_news, get_flow_data

Adapters MUST NOT import app-level modules at module scope to avoid circular
imports; use lazy function-scoped imports inside method bodies instead.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Union

import pandas as pd


class BaseExchangeAdapter(ABC):
    """Uniform interface for per-exchange data retrieval."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @abstractmethod
    def get_region(self) -> str:
        """Return the region/exchange code, e.g. 'US', 'HK', 'CN', 'JP', 'EU'."""
        ...

    # ------------------------------------------------------------------
    # Company info
    # ------------------------------------------------------------------

    @abstractmethod
    def get_metadata(self, ticker: str) -> dict:
        """
        Return company metadata dict.

        Expected keys (provide None / omit if unavailable):
            name, sector, industry, description, exchange, currency,
            country, website, employees, market_cap, logo_url
        """
        ...

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> dict:
        """
        Return key fundamental metrics dict.

        Expected keys (provide None / omit if unavailable):
            pe_ratio, pb_ratio, ps_ratio, ev_ebitda, ev_revenue,
            market_cap, enterprise_value, revenue_ttm, gross_profit_ttm,
            ebitda_ttm, net_income_ttm, cash, total_debt, beta,
            dividend_yield, shares_outstanding, float_shares,
            52wk_high, 52wk_low, avg_volume_30d
        """
        ...

    # ------------------------------------------------------------------
    # Price data
    # ------------------------------------------------------------------

    @abstractmethod
    def get_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Return OHLCV price DataFrame.

        Index   : DatetimeIndex (UTC-normalised)
        Columns : Open, High, Low, Close, Volume  (+ Adj Close where available)
        """
        ...

    # ------------------------------------------------------------------
    # Regulatory / disclosure data
    # ------------------------------------------------------------------

    def get_filings(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        """
        Return regulatory filings.

        Columns : date, title, type, url

        US  → SEC EDGAR  (TODO: full EDGAR integration)
        HK  → HKEXnews   (TODO: scraper stub in hk.py)

        Default raises NotImplementedError; override in subclass.
        """
        raise NotImplementedError(
            f"get_filings() is not implemented for region '{self.get_region()}'."
        )

    # ------------------------------------------------------------------
    # Biotech-specific: clinical trials
    # ------------------------------------------------------------------

    def get_trials(self, ticker: str) -> pd.DataFrame:
        """
        Return clinical trial data.

        Columns : nct_id, title, phase, status, condition,
                  start_date, primary_completion_date, enrollment, sponsor

        US  → ClinicalTrials.gov REST API v2
        HK  → company-name lookup on ClinicalTrials.gov (TODO)

        Default raises NotImplementedError; override in subclass.
        """
        raise NotImplementedError(
            f"get_trials() is not implemented for region '{self.get_region()}'."
        )

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        """
        Return recent news articles.

        Columns : date, title, source, url, summary

        Default raises NotImplementedError; override in subclass.
        """
        raise NotImplementedError(
            f"get_news() is not implemented for region '{self.get_region()}'."
        )

    # ------------------------------------------------------------------
    # Institutional / large-holder flow
    # ------------------------------------------------------------------

    def get_flow_data(self, ticker: str) -> pd.DataFrame:
        """
        Return institutional flow / shareholding data.

        US  → SEC 13F filings       (TODO: EDGAR form-13F API)
        HK  → CCASS shareholding    (TODO: CCASS HTML scraper in hk.py)

        Column schemas vary by region; document in each subclass.

        Default raises NotImplementedError; override in subclass.
        """
        raise NotImplementedError(
            f"get_flow_data() is not implemented for region '{self.get_region()}'."
        )

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} region={self.get_region()}>"
