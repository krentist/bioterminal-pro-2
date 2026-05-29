"""
alpha_screener.py — biotech/pharma alpha opportunity screener.

Scores tickers across five dimensions and returns a ranked table.
Works for both US and HK tickers via the exchange adapter pattern.

Scoring dimensions (each 0–20 pts, max 100):
    1. Momentum      – recent price vs SMA-50, RSI, 3-month return
    2. Value         – P/S, EV/Revenue relative to sector
    3. Pipeline      – phase-weighted trial count, catalysts within 12m
    4. Quality       – revenue growth, gross margin, cash runway
    5. Technical     – MACD histogram direction, BB position, volume spike
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from data_fetcher import (
    get_price_history,
    get_financial_metrics,
    get_pipeline_data,
)
from pipeline_analyzer import enrich_trials, upcoming_catalysts, PROB_TO_APPROVAL

logger = logging.getLogger(__name__)

# Default biotech universe for the screener
DEFAULT_US_UNIVERSE = [
    "MRNA", "BNTX", "REGN", "VRTX", "GILD", "AMGN", "BIIB",
    "SGEN", "ALNY", "IONS", "SAGE", "ARCT", "NVAX", "RCUS",
    "KYMR", "KRYS", "FOLD", "RARE", "BBIO", "AGEN",
]

DEFAULT_HK_UNIVERSE = [
    # Core GBA large-cap biotech
    "6160.HK",  # BeiGene / BeOne Medicines
    "2269.HK",  # WuXi Biologics
    "2359.HK",  # WuXi AppTec
    "1801.HK",  # Innovent Biologics
    "3692.HK",  # Hansoh Pharmaceutical
    "1093.HK",  # CSPC Pharmaceutical
    "1177.HK",  # Sino Biopharmaceutical
    "9688.HK",  # Zai Lab
    "0013.HK",  # HUTCHMED (China)
    # Oncology / antibody platforms
    "9995.HK",  # RemeGen
    "6963.HK",  # Akeso (bispecific antibodies, ivonescimab)
    "2577.HK",  # Junshi Biosciences (toripalimab PD-1)
    "2252.HK",  # Shanghai Henlius Biologic (biosimilars)
    "2137.HK",  # Adagene (antibody platform)
    "2119.HK",  # Bio-Thera Solutions (biosimilars)
    # CAR-T / cell & gene therapy
    "9987.HK",  # Legend Biotech (ciltacabtagene, CAR-T)
    # Small-molecule / specialty pharma
    "2096.HK",  # Simcere Pharmaceutical
    "2186.HK",  # Luye Pharma
    "0867.HK",  # China Medical System Holdings
    "2552.HK",  # Hua Medicine (GKA for T2D)
    "2176.HK",  # Gan & Lee Pharmaceuticals (insulin)
    "1530.HK",  # 3SBio (biologic therapeutics, EPO)
    # CRO / CDMO / tools
    "1873.HK",  # Viva Biotech (CRO / fragment-based drug discovery)
    "6998.HK",  # Genor Biopharma (biosimilars)
    # Pan-China pharma
    "2616.HK",  # CStone Pharmaceuticals
    "6185.HK",  # CanSino Biologics
    "2196.HK",  # Shanghai Fosun Pharma
]


# ---------------------------------------------------------------------------
# Per-dimension scoring functions  (each returns 0–20)
# ---------------------------------------------------------------------------

def _score_momentum(prices: pd.DataFrame) -> float:
    if prices.empty or len(prices) < 50:
        return 10.0
    closes = prices["Close"].astype(float)
    ret_3m = closes.pct_change(63).iloc[-1] if len(closes) >= 63 else 0.0
    sma50  = closes.rolling(50).mean().iloc[-1]
    px     = closes.iloc[-1]
    above_sma = 1 if px > sma50 else 0

    delta  = closes.diff()
    gain   = delta.clip(lower=0).rolling(14).mean()
    loss   = (-delta.clip(upper=0)).rolling(14).mean()
    rs     = gain / loss.replace(0, np.nan)
    rsi    = (100 - 100 / (1 + rs)).iloc[-1]

    score  = 10.0
    score += np.clip(ret_3m * 40, -8, 8)   # ±8 pts for ±20% momentum
    score += above_sma * 4                  # +4 for above SMA-50
    score += (rsi - 50) / 50 * 4           # ±4 for RSI deviation from 50
    return float(np.clip(score, 0, 20))


def _score_value(fundamentals: dict) -> float:
    ps    = fundamentals.get("ps_ratio")
    evrev = fundamentals.get("ev_revenue")
    score = 10.0
    # Lower P/S = more value
    if ps is not None and not np.isnan(ps):
        score += np.clip(4 - ps, -6, 6)     # ideal ≤4x, penalty for >10x
    if evrev is not None and not np.isnan(evrev):
        score += np.clip(5 - evrev, -6, 6)
    return float(np.clip(score, 0, 20))


def _score_pipeline(trials_df: pd.DataFrame) -> float:
    if trials_df.empty:
        return 5.0
    enriched = enrich_trials(trials_df)
    cats     = upcoming_catalysts(enriched, within_days=365)
    score    = 0.0
    # Phase-weighted active trial count
    for _, row in enriched[enriched["is_active"] == True].iterrows():
        p = row["prob_approval"]
        score += p * 20   # Phase 3 contributes ~10 pts, Phase 1 ~1.5 pts
    score = np.clip(score, 0, 15)
    # Catalyst bonus: up to 5 pts for catalysts in next 12m
    score += min(len(cats) * 1.5, 5)
    return float(np.clip(score, 0, 20))


def _score_quality(fundamentals: dict) -> float:
    score  = 10.0
    rev_g  = fundamentals.get("revenue_growth")
    margin = fundamentals.get("profit_margin")
    cash   = fundamentals.get("cash")
    debt   = fundamentals.get("total_debt")
    mktcap = fundamentals.get("market_cap")

    if rev_g is not None and not np.isnan(rev_g):
        score += np.clip(rev_g * 20, -6, 6)   # ±6 for ±30% growth
    if margin is not None and not np.isnan(margin):
        score += np.clip(margin * 10, -4, 4)
    # Cash runway relative to market cap
    if cash and mktcap and mktcap > 0:
        cash_ratio = cash / mktcap
        score += np.clip(cash_ratio * 10, 0, 4)
    return float(np.clip(score, 0, 20))


def _score_technical(prices: pd.DataFrame) -> float:
    if prices.empty or len(prices) < 26:
        return 10.0
    closes = prices["Close"].astype(float)
    vol    = prices["Volume"].astype(float).replace(0, np.nan)

    ema12  = closes.ewm(span=12, adjust=False).mean()
    ema26  = closes.ewm(span=26, adjust=False).mean()
    macd   = (ema12 - ema26)
    hist   = (macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1]

    sma20  = closes.rolling(20).mean().iloc[-1]
    std20  = closes.rolling(20).std().iloc[-1]
    bb_pos = (closes.iloc[-1] - sma20) / (2 * std20) if std20 else 0.0

    vol_ma = vol.rolling(20).mean().iloc[-1]
    vol_sp = vol.iloc[-1] / vol_ma if vol_ma else 1.0

    score  = 10.0
    score += np.clip(float(hist) * 5_000, -5, 5)   # MACD hist direction
    score += np.clip(-float(bb_pos) * 4, -4, 4)    # oversold = positive
    score += np.clip((float(vol_sp) - 1) * 2, -3, 3)  # volume spike
    return float(np.clip(score, 0, 20))


# ---------------------------------------------------------------------------
# Main screener
# ---------------------------------------------------------------------------

def score_ticker(ticker: str) -> Optional[dict]:
    """Score a single ticker; returns None on data failure."""
    try:
        prices = get_price_history(ticker, period="1y")
        funds  = get_financial_metrics(ticker)
        trials = get_pipeline_data(ticker)

        m = _score_momentum(prices)
        v = _score_value(funds)
        p = _score_pipeline(trials)
        q = _score_quality(funds)
        t = _score_technical(prices)

        total = m + v + p + q + t

        return {
            "ticker":           ticker,
            "total_score":      round(total, 1),
            "momentum":         round(m, 1),
            "value":            round(v, 1),
            "pipeline":         round(p, 1),
            "quality":          round(q, 1),
            "technical":        round(t, 1),
            "market_cap":       funds.get("market_cap"),
            "ps_ratio":         funds.get("ps_ratio"),
            "revenue_growth":   funds.get("revenue_growth"),
        }
    except Exception as exc:
        logger.warning("score_ticker(%s) failed: %s", ticker, exc)
        return None


def run_screen(
    universe: Optional[list[str]] = None,
    region:   str = "US",
    top_n:    int = 10,
) -> pd.DataFrame:
    """
    Screen a universe of tickers and return the top_n ranked by total score.

    Parameters
    ----------
    universe : list of ticker strings; defaults to DEFAULT_US_UNIVERSE or
               DEFAULT_HK_UNIVERSE based on region.
    region   : "US" or "HK" — selects default universe if none given.
    top_n    : number of tickers to return.
    """
    if universe is None:
        universe = DEFAULT_HK_UNIVERSE if region == "HK" else DEFAULT_US_UNIVERSE

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(score_ticker, t): t for t in universe}
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                results.append(row)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("total_score", ascending=False).head(top_n)
    df["rank"] = range(1, len(df) + 1)
    return df.reset_index(drop=True)
