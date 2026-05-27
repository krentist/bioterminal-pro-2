"""
Shared utilities: formatting, date helpers, exchange mapping, DataFrame helpers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Exchange / region mapping
# ---------------------------------------------------------------------------

# Explicit overrides; format heuristics handle everything else.
TICKER_EXCHANGE_MAP: dict[str, str] = {
    # HKEX biotech / pharma / tech
    "0700.HK": "HK",   # Tencent
    "9988.HK": "HK",   # Alibaba
    "3690.HK": "HK",   # Meituan
    "1177.HK": "HK",   # Sino Biopharmaceutical
    "1093.HK": "HK",   # CSPC Pharmaceutical
    "2269.HK": "HK",   # WuXi Biologics
    "6160.HK": "HK",   # BeiGene
    "2359.HK": "HK",   # WuXi AppTec
    "1801.HK": "HK",   # Innovent Biologics
    "3692.HK": "HK",   # Hansoh Pharmaceutical
    "2196.HK": "HK",   # Shanghai Fosun Pharmaceutical
    "0241.HK": "HK",   # Alibaba Health
    # TODO: extend from a config file or database as coverage grows
}


def get_exchange_for_ticker(ticker: str) -> str:
    """Return exchange code via explicit map, then suffix heuristics."""
    t = ticker.strip().upper()
    if t in TICKER_EXCHANGE_MAP:
        return TICKER_EXCHANGE_MAP[t]
    if t.endswith(".HK"):
        return "HK"
    if t.endswith(".SS") or t.endswith(".SZ"):
        return "CN"   # TODO: CNExchangeAdapter
    if t.endswith(".T"):
        return "JP"   # TODO: JPExchangeAdapter
    if t.endswith(".L") or t.endswith(".PA") or t.endswith(".DE") or t.endswith(".AS"):
        return "EU"   # TODO: EUExchangeAdapter
    if t.isdigit() and len(t) <= 5:
        return "HK"   # bare numeric HK code
    return "US"


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

CURRENCY_SYMBOLS = {"USD": "$", "HKD": "HK$", "CNY": "¥", "EUR": "€", "GBP": "£"}


def fmt_large(n, currency: str = "USD") -> str:
    """Format large numbers as $1.2B / HK$500M, etc."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    sym = CURRENCY_SYMBOLS.get(currency, "$")
    abs_n = abs(float(n))
    if abs_n >= 1e12:
        return f"{sym}{n/1e12:.2f}T"
    if abs_n >= 1e9:
        return f"{sym}{n/1e9:.2f}B"
    if abs_n >= 1e6:
        return f"{sym}{n/1e6:.2f}M"
    return f"{sym}{n:,.0f}"


def fmt_pct(v, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{float(v) * 100:.{decimals}f}%"


def fmt_ratio(v, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{float(v):.{decimals}f}x"


def fmt_num(v, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{float(v):.{decimals}f}"


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def period_to_dates(period: str = "1y") -> tuple[datetime, datetime]:
    """Convert a yfinance-style period string to (start, end) datetimes."""
    end = datetime.today()
    mapping = {
        "1mo":  timedelta(days=30),
        "3mo":  timedelta(days=91),
        "6mo":  timedelta(days=182),
        "1y":   timedelta(days=365),
        "2y":   timedelta(days=730),
        "5y":   timedelta(days=1825),
        "max":  timedelta(days=365 * 20),
    }
    return end - mapping.get(period, timedelta(days=365)), end


def parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise OHLCV DataFrame from yfinance; handle MultiIndex columns."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip() for c in df.columns]
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV DataFrame missing columns: {missing}")
    df.index = pd.to_datetime(df.index)
    df = df.dropna(subset=["Close"])
    return df


def safe_get(d: dict, *keys, default=None):
    """Safely traverse a nested dict."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def colour_delta(v: float) -> str:
    """Return CSS colour string for a numeric delta."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "#888888"
    return "#00c853" if float(v) >= 0 else "#ff3d00"
