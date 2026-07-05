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
    "6160.HK": "ONC",    # BeOne Medicines, formerly BeiGene (NASDAQ: ONC, active — BGNE→ONC 2025-01-02)
    # US → HK
    "ZLAB": "9688.HK",
    "HCM":  "0013.HK",
    "ONC":  "6160.HK",
}

# How many ordinary shares each ADS represents
ADS_RATIO: dict[str, float] = {
    "ZLAB": 10.0,   # 1 ADS = 10 ordinary shares
    "HCM":  5.0,    # 1 ADS = 5 ordinary shares
    "ONC":  13.0,   # 1 ADS = 13 ordinary shares (BeiGene/BeOne, unchanged since 2018)
}

# Tickers with terminated US ADS programs — shown as historical context, not live prices.
# (BeiGene did NOT delist: it renamed to BeOne Medicines and its Nasdaq ticker changed
# BGNE→ONC on 2025-01-02; it is an active dual-listing above.)
DELISTED_ADS: dict[str, dict] = {}

_USDHKD_TICKER = "USDHKD=X"
_USDCNY_TICKER = "USDCNY=X"

# A/H/US cross-border groups — each company's share classes across exchanges.
# Every leg below was verified to resolve to the same entity on yfinance.
# `ads_ratio` = ordinary shares per US ADS (only where a US ADS leg exists).
CROSS_BORDER_GROUPS: list[dict] = [
    {"name": "BeOne Medicines (BeiGene)",          "hk": "6160.HK", "us": "ONC", "cn": "688235.SS", "ads_ratio": 13.0},
    {"name": "Shanghai Junshi Biosciences",        "hk": "1877.HK", "cn": "688180.SS"},
    {"name": "CanSino Biologics",                  "hk": "6185.HK", "cn": "688185.SS"},
    {"name": "WuXi AppTec",                        "hk": "2359.HK", "cn": "603259.SS"},
    {"name": "Shanghai Fosun Pharmaceutical",      "hk": "2196.HK", "cn": "600196.SS"},
    {"name": "Jiangsu Hengrui Pharmaceuticals",    "hk": "1276.HK", "cn": "600276.SS"},
]

# ticker (upper) → its group, for O(1) lookup from any leg
_CROSS_BORDER_INDEX: dict[str, dict] = {}
for _g in CROSS_BORDER_GROUPS:
    for _leg in ("hk", "us", "cn"):
        if _g.get(_leg):
            _CROSS_BORDER_INDEX[_g[_leg].upper()] = _g


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


def _usdcny_rate() -> float:
    try:
        info = yf.Ticker(_USDCNY_TICKER).info or {}
        rate = info.get("regularMarketPrice") or info.get("currentPrice")
        if rate:
            return float(rate)
    except Exception:
        pass
    return 7.15  # fallback: typical USD/CNY rate


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


def get_cross_border_info(ticker: str) -> dict | None:
    """Full A/H/US cross-listing view for a company: every share class it lists across
    Shanghai/Shenzhen (CN), Hong Kong (HK), and the US, each priced on a common
    per-ordinary-share USD basis with a premium/discount vs. the reference leg.

    Returns None if the ticker is not in a known cross-border group.
    """
    t = ticker.strip().upper()
    group = _CROSS_BORDER_INDEX.get(t)
    if not group:
        return None

    usdhkd = _usdhkd_rate()
    usdcny = _usdcny_rate()
    ads_ratio = float(group.get("ads_ratio", 1.0))

    def _per_share_usd(exch: str, price: float | None) -> float | None:
        if not price:
            return None
        if exch == "HK":
            return price / usdhkd
        if exch == "CN":
            return price / usdcny
        if exch == "US":                      # ADS → per ordinary share
            return price / ads_ratio
        return None

    legs: list[dict] = []
    for exch, key, currency in (("CN", "cn", "CNY"), ("HK", "hk", "HKD"), ("US", "us", "USD")):
        tk = group.get(key)
        if not tk:
            continue
        price = _fetch_price(tk)
        leg = {
            "exchange":        exch,
            "ticker":          tk.upper(),
            "currency":        currency,
            "priceLocal":      round(price, 4) if price else None,
            "pricePerShareUsd": None,
            "premiumVsRefPct": None,
        }
        if exch == "US":
            leg["adsRatio"] = ads_ratio
        psu = _per_share_usd(exch, price)
        leg["pricePerShareUsd"] = round(psu, 4) if psu else None
        legs.append(leg)

    # Reference = HK leg if present (the GBA anchor), else the first leg with a USD price.
    ref = next((l for l in legs if l["exchange"] == "HK" and l["pricePerShareUsd"]), None)
    if ref is None:
        ref = next((l for l in legs if l["pricePerShareUsd"]), None)
    if ref is not None:
        ref_usd = ref["pricePerShareUsd"]
        for l in legs:
            if l["pricePerShareUsd"] and ref_usd:
                l["premiumVsRefPct"] = round((l["pricePerShareUsd"] / ref_usd - 1) * 100, 2)

    return {
        "ticker":            t,
        "cross_border":      True,
        "name":              group["name"],
        "referenceExchange": ref["exchange"] if ref else None,
        "usdhkd_rate":       round(usdhkd, 4),
        "usdcny_rate":       round(usdcny, 4),
        "legs":              legs,
        "listedExchanges":   [l["exchange"] for l in legs],
        "source":            "Yahoo Finance",
    }
