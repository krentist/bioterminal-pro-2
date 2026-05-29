"""
dual_listing.py — cross-border dual-listing detection and premium/discount calculator.

Covers HK-listed biotechs that also trade on US exchanges (NASDAQ/NYSE) as ADSs.
The map is bidirectional: look up either the HK or US ticker to find the counterpart.
"""
from __future__ import annotations

import logging

import yfinance as yf

logger = logging.getLogger(__name__)

# Active dual-listings — bidirectional HK ↔ US ticker pairs.
# Only include pairs where the US ADS is currently trading.
DUAL_LISTED: dict[str, str] = {
    # HK → US
    "9688.HK": "ZLAB",   # Zai Lab (NASDAQ: ZLAB, active)
    "0013.HK": "HCM",    # HUTCHMED (NASDAQ: HCM, active)
    # US → HK
    "ZLAB": "9688.HK",
    "HCM":  "0013.HK",
}

# How many ordinary shares each ADS represents
ADS_RATIO: dict[str, float] = {
    "ZLAB": 10.0,   # 1 ADS = 10 ordinary shares
    "HCM":  5.0,    # 1 ADS = 5 ordinary shares
}

# Tickers with terminated US ADS programs — shown as historical context, not live prices
DELISTED_ADS: dict[str, dict] = {
    "6160.HK": {
        "us_ticker": "BGNE",
        "delisted_date": "2024-08-22",
        "exchange": "NASDAQ",
        "note": "BeiGene voluntarily delisted its US ADS from NASDAQ in August 2024. "
                "The HK listing (6160.HK) remains active.",
    },
    "BGNE": {
        "hk_ticker": "6160.HK",
        "delisted_date": "2024-08-22",
        "exchange": "NASDAQ",
        "note": "BeiGene voluntarily delisted its US ADS from NASDAQ in August 2024. "
                "The HK listing (6160.HK) remains active.",
    },
}

_USDHKD_TICKER = "USDHKD=X"


def _fetch_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info or {}
        px = info.get("regularMarketPrice") or info.get("currentPrice")
        if px:
            return float(px)
        hist = yf.Ticker(ticker).history(period="2d", auto_adjust=True)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.error("dual_listing price(%s): %s", ticker, exc)
    return None


def _usdhkd_rate() -> float:
    try:
        info = yf.Ticker(_USDHKD_TICKER).info or {}
        rate = info.get("regularMarketPrice") or info.get("currentPrice")
        if rate:
            return float(rate)
    except Exception:
        pass
    return 7.78  # fallback: typical HKD/USD peg rate


def get_dual_listing_info(ticker: str) -> dict | None:
    """
    Return dual-listing data for a ticker, or None if not dual-listed.

    Also returns delisted ADS history for tickers like BeiGene/BGNE whose US
    program was terminated, so the frontend can show an informative state.

    Response keys (active):
        ticker, counterpart_ticker, hk_ticker, us_ticker,
        hk_price_hkd, us_price_usd, us_price_hkd,
        premium_discount_pct, usdhkd_rate, status="active"

    Response keys (delisted):
        ticker, status="delisted", delisted_date, note
    """
    t = ticker.strip().upper()

    # Check for terminated ADS program first
    delisted = DELISTED_ADS.get(t)
    if delisted:
        return {"ticker": t, "status": "delisted", **delisted}

    counterpart = DUAL_LISTED.get(t)
    if not counterpart:
        return None

    is_hk_input = t.endswith(".HK")
    hk_ticker = t if is_hk_input else counterpart
    us_ticker  = counterpart if is_hk_input else t

    us_ticker_clean = us_ticker  # e.g. "BGNE"
    ads_ratio = ADS_RATIO.get(us_ticker_clean, 1.0)

    hk_price = _fetch_price(hk_ticker)
    us_price  = _fetch_price(us_ticker_clean)
    rate      = _usdhkd_rate()

    # Convert US price to HKD for comparison (adjusted for ADS ratio)
    us_price_hkd = (us_price * rate / ads_ratio) if us_price else None

    premium_discount = None
    if hk_price and us_price_hkd and us_price_hkd > 0:
        premium_discount = round((hk_price / us_price_hkd - 1) * 100, 2)

    return {
        "ticker":               t,
        "counterpart_ticker":   counterpart,
        "hk_ticker":            hk_ticker,
        "us_ticker":            us_ticker_clean,
        "hk_price_hkd":         round(hk_price, 4) if hk_price else None,
        "us_price_usd":         round(us_price, 4) if us_price else None,
        "us_price_hkd":         round(us_price_hkd, 4) if us_price_hkd else None,
        "premium_discount_pct": premium_discount,
        "usdhkd_rate":          round(rate, 4),
        "ads_ratio":            ads_ratio,
        "status":               "active",
    }
