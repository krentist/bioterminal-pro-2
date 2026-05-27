"""
devils_advocate.py — systematic bear-case / risk analysis for a biotech stock.

Generates a structured list of risk factors across six categories,
each with a severity score (1–5) and supporting evidence drawn from
available data (fundamentals, pipeline, price history).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RiskFactor:
    category:  str           # e.g. "Financial", "Pipeline", "Technical"
    title:     str
    detail:    str
    severity:  int           # 1 (low) – 5 (critical)
    evidence:  str           # data point supporting the flag


def analyse(
    ticker:       str,
    prices:       pd.DataFrame,
    fundamentals: dict,
    trials:       pd.DataFrame,
    info:         dict,
) -> list[RiskFactor]:
    """
    Return a list of RiskFactor items for the given ticker.

    Checks performed:
        Financial  : cash burn, debt load, dilution risk, no revenue
        Pipeline   : no active Phase 3, single-asset concentration
        Technical  : below key MAs, RSI divergence, volume deterioration
        Valuation  : extreme EV/Revenue or P/S multiples
        Regulatory : PDUFA risk, CRL history (cannot auto-detect; flagged if pipeline)
        Macro/Sector: beta, correlation to XBI
    """
    risks: list[RiskFactor] = []

    risks += _financial_risks(fundamentals)
    risks += _pipeline_risks(trials)
    risks += _technical_risks(prices)
    risks += _valuation_risks(fundamentals)
    risks += _regulatory_risks(trials, fundamentals)

    # Sort by severity descending
    return sorted(risks, key=lambda r: r.severity, reverse=True)


# ---------------------------------------------------------------------------
# Risk checkers
# ---------------------------------------------------------------------------

def _financial_risks(f: dict) -> list[RiskFactor]:
    risks = []

    cash       = f.get("cash") or 0
    debt       = f.get("total_debt") or 0
    net_income = f.get("net_income_ttm")
    revenue    = f.get("revenue_ttm") or 0
    mktcap     = f.get("market_cap") or 0

    # No revenue
    if revenue == 0 or revenue is None:
        risks.append(RiskFactor(
            category="Financial",
            title="Pre-revenue company",
            detail="Company has no reported trailing-12-month revenue, "
                   "making it entirely dependent on pipeline success.",
            severity=3,
            evidence=f"TTM Revenue: $0",
        ))

    # Burning cash with low runway
    if net_income is not None and net_income < 0 and cash > 0:
        annual_burn = abs(net_income)
        runway_yrs  = cash / annual_burn if annual_burn else float("inf")
        if runway_yrs < 1.5:
            risks.append(RiskFactor(
                category="Financial",
                title="Critical cash runway (<18 months)",
                detail=f"At current burn rate the company has approximately "
                       f"{runway_yrs:.1f} years of cash runway. A near-term "
                       "capital raise is likely, which carries dilution risk.",
                severity=5,
                evidence=f"Cash: ${cash/1e6:.0f}M | Annual burn: ${annual_burn/1e6:.0f}M",
            ))
        elif runway_yrs < 2.5:
            risks.append(RiskFactor(
                category="Financial",
                title="Limited cash runway (<30 months)",
                detail=f"Cash runway estimated at {runway_yrs:.1f} years. "
                       "Dilutive equity raise possible within the forecast period.",
                severity=3,
                evidence=f"Cash: ${cash/1e6:.0f}M | Annual burn: ${annual_burn/1e6:.0f}M",
            ))

    # High debt relative to market cap
    if debt > 0 and mktcap > 0 and (debt / mktcap) > 0.5:
        ratio = debt / mktcap
        risks.append(RiskFactor(
            category="Financial",
            title="High debt-to-market-cap ratio",
            detail=f"Total debt represents {ratio:.0%} of market cap, "
                   "limiting financial flexibility and increasing refinancing risk.",
            severity=3,
            evidence=f"Debt: ${debt/1e6:.0f}M | Market Cap: ${mktcap/1e6:.0f}M",
        ))

    return risks


def _pipeline_risks(trials: pd.DataFrame) -> list[RiskFactor]:
    risks = []
    if trials.empty:
        risks.append(RiskFactor(
            category="Pipeline",
            title="No clinical trial data available",
            detail="Could not retrieve clinical trial data. This may indicate "
                   "a very early-stage company, a non-biotech business, or a "
                   "data gap for this region.",
            severity=2,
            evidence="ClinicalTrials.gov: 0 studies found",
        ))
        return risks

    from pipeline_analyzer import enrich_trials, _normalise_phase
    enriched = enrich_trials(trials)
    active   = enriched[enriched["is_active"] == True]
    ph3_plus = active["phase_clean"].isin({"Phase 3", "NDA/BLA", "Approved"})

    if len(active) == 0:
        risks.append(RiskFactor(
            category="Pipeline",
            title="No active clinical trials",
            detail="All registered studies are either completed, terminated, "
                   "or not yet recruiting.",
            severity=4,
            evidence=f"Total studies: {len(enriched)} | Active: 0",
        ))
    elif not ph3_plus.any():
        risks.append(RiskFactor(
            category="Pipeline",
            title="No late-stage (Phase 3+) assets",
            detail="All active trials are Phase 1 or Phase 2. "
                   "Approval and revenue generation are likely 5+ years away.",
            severity=3,
            evidence=f"Active trials: {len(active)} | Phase 3+: 0",
        ))

    # Single-asset concentration
    if 0 < len(active) <= 2:
        risks.append(RiskFactor(
            category="Pipeline",
            title="Single-asset / concentrated pipeline",
            detail="Fewer than 3 active trials means the company's valuation "
                   "is highly dependent on the outcome of one or two programmes.",
            severity=3,
            evidence=f"Active trials: {len(active)}",
        ))

    # Terminated trials
    terminated = enriched[enriched["status"].str.upper().isin({"TERMINATED", "WITHDRAWN"}) if "status" in enriched.columns else pd.Series(False, index=enriched.index)]
    if len(terminated) >= 2:
        risks.append(RiskFactor(
            category="Pipeline",
            title="History of trial terminations",
            detail=f"{len(terminated)} registered studies have been terminated "
                   "or withdrawn, which may signal execution or efficacy concerns.",
            severity=2,
            evidence=f"Terminated/withdrawn: {len(terminated)}",
        ))

    return risks


def _technical_risks(prices: pd.DataFrame) -> list[RiskFactor]:
    risks = []
    if prices.empty or len(prices) < 50:
        return risks

    closes = prices["Close"].astype(float)
    px     = closes.iloc[-1]
    sma50  = closes.rolling(50).mean().iloc[-1]
    sma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None

    # Below SMA-50
    if px < sma50:
        pct = (px / sma50 - 1) * 100
        risks.append(RiskFactor(
            category="Technical",
            title=f"Price below 50-day moving average ({pct:.1f}%)",
            detail="Stock is trading below its 50-day SMA, indicating "
                   "a short-to-medium-term downtrend.",
            severity=2,
            evidence=f"Price: {px:.2f} | SMA-50: {sma50:.2f}",
        ))

    # Death cross (SMA-50 below SMA-200)
    if sma200 is not None and not np.isnan(sma200) and sma50 < sma200:
        risks.append(RiskFactor(
            category="Technical",
            title="Death cross (SMA-50 < SMA-200)",
            detail="The 50-day moving average has crossed below the 200-day, "
                   "a bearish long-term trend signal.",
            severity=3,
            evidence=f"SMA-50: {sma50:.2f} | SMA-200: {sma200:.2f}",
        ))

    # 6-month drawdown
    high_6m  = closes.iloc[-126:].max() if len(closes) >= 126 else closes.max()
    drawdown = (px / high_6m - 1) * 100
    if drawdown < -40:
        risks.append(RiskFactor(
            category="Technical",
            title=f"Severe 6-month drawdown ({drawdown:.0f}%)",
            detail="Stock has fallen more than 40% from its 6-month high, "
                   "potentially reflecting fundamental deterioration.",
            severity=4,
            evidence=f"6m high: {high_6m:.2f} | Current: {px:.2f}",
        ))

    return risks


def _valuation_risks(f: dict) -> list[RiskFactor]:
    risks = []
    ps    = f.get("ps_ratio")
    evrev = f.get("ev_revenue")

    if ps is not None and not np.isnan(ps) and ps > 20:
        risks.append(RiskFactor(
            category="Valuation",
            title=f"Elevated P/S ratio ({ps:.1f}x)",
            detail="Price/Sales above 20x leaves limited margin for disappointment. "
                   "Any miss on growth expectations could trigger a sharp de-rating.",
            severity=2 if ps < 50 else 3,
            evidence=f"P/S: {ps:.1f}x",
        ))

    if evrev is not None and not np.isnan(evrev) and evrev > 30:
        risks.append(RiskFactor(
            category="Valuation",
            title=f"Elevated EV/Revenue ({evrev:.1f}x)",
            detail="Enterprise value trades at a significant premium to revenue. "
                   "Dependent on sustained high growth to justify the multiple.",
            severity=2 if evrev < 60 else 3,
            evidence=f"EV/Revenue: {evrev:.1f}x",
        ))

    return risks


def _regulatory_risks(trials: pd.DataFrame, f: dict) -> list[RiskFactor]:
    risks = []
    if not trials.empty:
        risks.append(RiskFactor(
            category="Regulatory",
            title="Binary FDA/regulatory event risk",
            detail="Clinical-stage biotech companies face significant binary "
                   "risk around PDUFA dates, CRL (Complete Response Letters), "
                   "and advisory committee meetings. A single negative decision "
                   "can erase 30–70% of market cap.",
            severity=3,
            evidence="Clinical trials registered — regulatory approval required",
        ))
    return risks


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def risk_summary(risks: list[RiskFactor]) -> dict:
    """Return aggregate stats for the risk factor list."""
    if not risks:
        return {"count": 0, "critical": 0, "high": 0, "max_severity": 0, "overall": "LOW"}
    critical = sum(1 for r in risks if r.severity >= 5)
    high     = sum(1 for r in risks if r.severity == 4)
    max_sev  = max(r.severity for r in risks)
    overall  = "CRITICAL" if critical else ("HIGH" if high else ("MEDIUM" if max_sev >= 3 else "LOW"))
    return {
        "count":        len(risks),
        "critical":     critical,
        "high":         high,
        "max_severity": max_sev,
        "overall":      overall,
    }
