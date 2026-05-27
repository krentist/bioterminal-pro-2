"""
exchanges – region-aware data-adapter package.

Public API
----------
get_exchange_adapter(ticker) -> BaseExchangeAdapter
    Factory: returns the correct adapter for the given ticker string.

Currently supported regions
----------------------------
US  – USExchangeAdapter   (yfinance + ClinicalTrials.gov)
HK  – HKExchangeAdapter   (yfinance; CCASS / HKEXnews stubs)

Planned (not yet implemented)
------------------------------
# from .eu import EUExchangeAdapter
# from .cn import CNExchangeAdapter
# from .jp import JPExchangeAdapter
"""
from __future__ import annotations

from .base import BaseExchangeAdapter
from .us import USExchangeAdapter
from .hk import HKExchangeAdapter

# Extend this set as more tickers are confirmed to be HK-listed.
_KNOWN_HK = {
    "0700.HK", "9988.HK", "3690.HK",
    "1177.HK", "1093.HK", "2269.HK",
    "6160.HK", "2359.HK", "1801.HK",
    "3692.HK", "2196.HK", "0241.HK",
    "0941.HK", "2318.HK", "0005.HK",
    "1299.HK", "0883.HK", "0388.HK",
}


def get_exchange_adapter(ticker: str) -> BaseExchangeAdapter:
    """
    Return the appropriate exchange adapter for *ticker*.

    Dispatch order
    --------------
    1. Explicit ".HK" suffix              → HKExchangeAdapter
    2. Pure numeric string (≤ 5 digits)   → HKExchangeAdapter (bare HK code)
    3. Known-HK set membership            → HKExchangeAdapter
    4. Future: ".SS" / ".SZ"              → CNExchangeAdapter  (TODO)
    5. Future: ".T"                        → JPExchangeAdapter  (TODO)
    6. Future: ".L" / ".PA" / ".DE"       → EUExchangeAdapter  (TODO)
    7. Default                             → USExchangeAdapter
    """
    t = ticker.strip().upper()

    if t.endswith(".HK"):
        return HKExchangeAdapter()

    if t.isdigit() and len(t) <= 5:
        return HKExchangeAdapter()

    if t in _KNOWN_HK:
        return HKExchangeAdapter()

    # TODO: elif t.endswith(".SS") or t.endswith(".SZ"): return CNExchangeAdapter()
    # TODO: elif t.endswith(".T"):                        return JPExchangeAdapter()
    # TODO: elif t.endswith((".L", ".PA", ".DE", ".AS")): return EUExchangeAdapter()

    return USExchangeAdapter()


__all__ = [
    "BaseExchangeAdapter",
    "USExchangeAdapter",
    "HKExchangeAdapter",
    "get_exchange_adapter",
]
