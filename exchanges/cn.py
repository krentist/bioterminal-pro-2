"""
Mainland China (SSE / SZSE, incl. STAR Market) adapter — Phase M / §3.

Data sources:
- Prices / metadata / fundamentals : yfinance ('.SS' Shanghai, '.SZ' Shenzhen tickers)
- News                              : yfinance news feed
- Clinical trials                   : ClinicalTrials.gov (by company name — China biotechs
                                       register their global trials there)

Deliberately NOT implemented (no free, machine-readable, redistributable source exists):
- get_filings   → SSE/SZSE disclosure portals are interactive/Chinese-only forms
- get_flow_data → no A-share equivalent of CCASS is freely machine-readable

NMPA drug-approval status is exposed separately via the honest deep-link `/api/nmpa/{ticker}`
route, not fabricated here.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from .base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class CNExchangeAdapter(BaseExchangeAdapter):
    """Adapter for Shanghai/Shenzhen-listed equities (A-shares, incl. STAR Market)."""

    def get_region(self) -> str:
        return "CN"

    def _normalize_ticker(self, ticker: str) -> str:
        """Normalise to yfinance A-share format.

        '.SS'/'.SZ' pass through; a bare 6-digit code is routed by prefix — SSE codes
        start 6/9 ('600276' → '600276.SS'), SZSE codes start 0/2/3 ('300760' → '300760.SZ').
        """
        t = ticker.strip().upper()
        if t.endswith(".SS") or t.endswith(".SZ"):
            return t
        if t.isdigit() and len(t) == 6:
            return f"{t}.SS" if t[0] in ("6", "9") else f"{t}.SZ"
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

    def get_news(self, ticker: str, limit: int = 50) -> pd.DataFrame:
        from data_fetcher import fetch_yfinance_news
        return fetch_yfinance_news(self._normalize_ticker(ticker), limit)
