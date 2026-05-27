"""
earnings_analyzer.py — earnings history, surprise analysis, and guidance tracker.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def get_earnings_data(ticker: str) -> dict:
    """
    Return a dict with:
        quarterly_eps   : pd.DataFrame  (Date, Reported EPS, Estimated EPS, Surprise %)
        annual_revenue  : pd.DataFrame  (Year, Revenue, YoY growth)
        next_date       : str | None     (next earnings date if available)
        calendar        : dict | None    (yfinance earnings calendar)
    """
    t = yf.Ticker(ticker)

    # --- Quarterly earnings ---
    try:
        qe = t.quarterly_earnings
    except Exception:
        qe = None

    eps_df = pd.DataFrame()
    if qe is not None and not qe.empty:
        eps_df = qe.copy().reset_index()
        if "Reported EPS" in eps_df.columns and "Estimated EPS" in eps_df.columns:
            eps_df["Surprise %"] = (
                (eps_df["Reported EPS"] - eps_df["Estimated EPS"])
                / eps_df["Estimated EPS"].abs().replace(0, np.nan) * 100
            )
            eps_df["Beat"] = eps_df["Surprise %"] > 0

    # --- Annual revenue trend ---
    rev_df = pd.DataFrame()
    try:
        income = t.income_stmt
        if income is not None and not income.empty:
            rev_row = income.loc["Total Revenue"] if "Total Revenue" in income.index else None
            if rev_row is not None:
                rev_df = rev_row.T.reset_index()
                rev_df.columns = ["Date", "Revenue"]
                rev_df = rev_df.sort_values("Date")
                rev_df["YoY Growth %"] = rev_df["Revenue"].pct_change() * 100
    except Exception:
        pass

    # --- Next earnings date ---
    next_date = None
    calendar  = None
    try:
        cal = t.calendar
        if cal is not None:
            calendar = cal
            if "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                if hasattr(dates, "__iter__"):
                    today = pd.Timestamp.today()
                    future = [d for d in dates if pd.Timestamp(d) > today]
                    next_date = str(future[0].date()) if future else None
                else:
                    next_date = str(dates)
    except Exception:
        pass

    return {
        "quarterly_eps":  eps_df,
        "annual_revenue": rev_df,
        "next_date":      next_date,
        "calendar":       calendar,
    }


def get_analyst_estimates(ticker: str) -> dict:
    """Return analyst price target and recommendation data."""
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception:
        info = {}

    return {
        "target_mean":   info.get("targetMeanPrice"),
        "target_high":   info.get("targetHighPrice"),
        "target_low":    info.get("targetLowPrice"),
        "target_median": info.get("targetMedianPrice"),
        "recommendation":info.get("recommendationKey", "").upper(),
        "n_analysts":    info.get("numberOfAnalystOpinions"),
    }


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def beat_rate(eps_df: pd.DataFrame, last_n: int = 8) -> float:
    """Return EPS beat rate over last_n quarters (0–1)."""
    if eps_df.empty or "Beat" not in eps_df.columns:
        return np.nan
    recent = eps_df.head(last_n)
    valid  = recent["Beat"].dropna()
    return float(valid.mean()) if not valid.empty else np.nan


def avg_surprise_pct(eps_df: pd.DataFrame, last_n: int = 8) -> float:
    """Return average EPS surprise % over last_n quarters."""
    if eps_df.empty or "Surprise %" not in eps_df.columns:
        return np.nan
    recent = eps_df.head(last_n)["Surprise %"].dropna()
    return float(recent.mean()) if not recent.empty else np.nan


def revenue_cagr(rev_df: pd.DataFrame, years: int = 3) -> float:
    """Compute revenue CAGR over *years* (0.xx format)."""
    if rev_df.empty or "Revenue" not in rev_df.columns or len(rev_df) < 2:
        return np.nan
    sorted_df = rev_df.sort_values("Date")
    end_rev   = sorted_df["Revenue"].iloc[-1]
    start_rev = sorted_df["Revenue"].iloc[max(0, len(sorted_df) - years - 1)]
    if start_rev <= 0:
        return np.nan
    actual_yrs = min(years, len(sorted_df) - 1)
    return float((end_rev / start_rev) ** (1 / actual_yrs) - 1)


def earnings_summary(ticker: str) -> dict:
    """High-level earnings summary dict for the dashboard."""
    data   = get_earnings_data(ticker)
    eps_df = data["quarterly_eps"]
    rev_df = data["annual_revenue"]
    ests   = get_analyst_estimates(ticker)

    return {
        "next_earnings_date": data["next_date"],
        "beat_rate_8q":       beat_rate(eps_df),
        "avg_surprise_pct":   avg_surprise_pct(eps_df),
        "revenue_cagr_3y":    revenue_cagr(rev_df, 3),
        "target_mean":        ests["target_mean"],
        "target_high":        ests["target_high"],
        "target_low":         ests["target_low"],
        "recommendation":     ests["recommendation"],
        "n_analysts":         ests["n_analysts"],
        "quarterly_eps_df":   eps_df,
        "annual_revenue_df":  rev_df,
    }
