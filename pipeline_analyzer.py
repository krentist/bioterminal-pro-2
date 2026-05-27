"""
pipeline_analyzer.py — clinical trial pipeline analysis.

Consumes the raw trials DataFrame from data_fetcher.get_pipeline_data()
and produces enriched summaries, phase breakdowns, and catalyst timelines.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Industry-average phase transition probabilities  (BIO/Informa 2023 report)
# ---------------------------------------------------------------------------
PHASE_SUCCESS_RATES: dict[str, float] = {
    "Phase 1":       0.524,   # Ph1 → Ph2
    "Phase 2":       0.285,   # Ph2 → Ph3
    "Phase 3":       0.576,   # Ph3 → NDA/BLA
    "NDA/BLA":       0.853,   # NDA → Approval
    "Approved":      1.000,
}

# Cumulative probability of reaching approval FROM each phase
PROB_TO_APPROVAL: dict[str, float] = {
    "Phase 1":  0.524 * 0.285 * 0.576 * 0.853,   # ≈ 7.3%
    "Phase 2":  0.285 * 0.576 * 0.853,            # ≈ 14.0%
    "Phase 3":  0.576 * 0.853,                    # ≈ 49.1%
    "NDA/BLA":  0.853,
    "Approved": 1.000,
}

_PHASE_ORDER = ["Phase 1", "Phase 2", "Phase 3", "NDA/BLA", "Approved", "Other"]

_STATUS_ACTIVE = {"RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"}
_STATUS_COMPLETE = {"COMPLETED"}
_STATUS_TERMINATED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}


def enrich_trials(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns to the raw trials DataFrame:
        phase_clean     – normalised phase label
        status_clean    – title-case status
        is_active       – bool
        prob_approval   – float  (cumulative probability to approval)
        days_to_primary – int    (calendar days from today to primary_completion_date)
    """
    if df.empty:
        return df

    df = df.copy()
    df["phase_clean"] = df["phase"].apply(_normalise_phase)
    df["status_clean"] = df["status"].apply(
        lambda s: s.replace("_", " ").title() if isinstance(s, str) else "Unknown"
    )
    df["is_active"] = df["status"].apply(
        lambda s: str(s).upper() in _STATUS_ACTIVE if s else False
    )
    df["prob_approval"] = df["phase_clean"].map(PROB_TO_APPROVAL).fillna(0.0)

    today = datetime.today()
    df["days_to_primary"] = df["primary_completion_date"].apply(
        lambda d: _days_to(d, today)
    )
    return df


def phase_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Return a count + percentage table by phase (active trials only)."""
    if df.empty:
        return pd.DataFrame(columns=["phase", "count", "pct"])
    active = df[df["is_active"] == True] if "is_active" in df.columns else df
    counts = active["phase_clean"].value_counts().reset_index()
    counts.columns = ["phase", "count"]
    counts["pct"] = counts["count"] / counts["count"].sum() * 100
    # Sort by clinical-stage order
    counts["_order"] = counts["phase"].map(
        {p: i for i, p in enumerate(_PHASE_ORDER)}
    ).fillna(99)
    return counts.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)


def upcoming_catalysts(df: pd.DataFrame, within_days: int = 365) -> pd.DataFrame:
    """
    Return trials whose primary_completion_date falls within *within_days* days.
    Sorted by proximity (nearest first).
    """
    if df.empty or "days_to_primary" not in df.columns:
        return df
    mask = (df["days_to_primary"] >= 0) & (df["days_to_primary"] <= within_days)
    return (
        df[mask]
        .sort_values("days_to_primary")
        .reset_index(drop=True)
    )


def pipeline_summary(df: pd.DataFrame) -> dict:
    """Return high-level pipeline summary statistics."""
    if df.empty:
        return {
            "total": 0, "active": 0,
            "phase3_plus": 0, "catalysts_12m": 0,
            "highest_phase": "N/A",
        }
    enriched = enrich_trials(df)
    cats = upcoming_catalysts(enriched, within_days=365)
    phase3_statuses = {"Phase 3", "NDA/BLA", "Approved"}
    return {
        "total":         len(enriched),
        "active":        int(enriched["is_active"].sum()),
        "phase3_plus":   int(enriched["phase_clean"].isin(phase3_statuses).sum()),
        "catalysts_12m": len(cats),
        "highest_phase": _highest_phase(enriched),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_phase(raw: Optional[str]) -> str:
    if not raw or str(raw).strip().upper() in ("N/A", "NA", "NONE", "NAN"):
        return "Other"
    s = str(raw).upper()
    if "PHASE 4" in s or "PHASE4" in s:
        return "Phase 4"
    if "PHASE 3" in s or "PHASE3" in s:
        return "Phase 3"
    if "PHASE 2" in s or "PHASE2" in s:
        return "Phase 2"
    if "PHASE 1" in s or "PHASE1" in s:
        return "Phase 1"
    if "NDA" in s or "BLA" in s or "MAA" in s:
        return "NDA/BLA"
    if "APPROV" in s:
        return "Approved"
    return "Other"


def _days_to(date_str: Optional[str], today: datetime) -> int:
    """Return calendar days from today to date_str; -1 if past / unparseable."""
    if not date_str:
        return -1
    for fmt in ("%Y-%m-%d", "%B %Y", "%Y-%m", "%Y"):
        try:
            d = datetime.strptime(str(date_str), fmt)
            delta = (d - today).days
            return max(delta, -1)
        except ValueError:
            continue
    return -1


def _highest_phase(df: pd.DataFrame) -> str:
    order = {p: i for i, p in enumerate(_PHASE_ORDER)}
    phases = df["phase_clean"].unique()
    sorted_phases = sorted(phases, key=lambda p: order.get(p, 99))
    return sorted_phases[-1] if sorted_phases else "N/A"
