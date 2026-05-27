"""Unit tests for pipeline_analyzer.py."""
import pandas as pd
import pytest

from pipeline_analyzer import (
    PROB_TO_APPROVAL,
    _normalise_phase,
    enrich_trials,
    upcoming_catalysts,
    pipeline_summary,
)


# ---------------------------------------------------------------------------
# _normalise_phase
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Phase 1",       "Phase 1"),
    ("PHASE1",        "Phase 1"),
    ("Phase 2",       "Phase 2"),
    ("Phase 2/3",     "Phase 2"),
    ("Phase 3",       "Phase 3"),
    ("PHASE 3",       "Phase 3"),
    ("Phase 1/2",     "Phase 1"),
    ("Phase 4",       "Phase 4"),
    ("NDA",           "NDA/BLA"),
    ("BLA",           "NDA/BLA"),
    ("MAA",           "NDA/BLA"),
    ("Approved",      "Approved"),
    ("APPROVED",      "Approved"),
    ("N/A",           "Other"),
    (None,            "Other"),
    ("",              "Other"),
    ("Observational", "Other"),
])
def test_normalise_phase(raw, expected):
    assert _normalise_phase(raw) == expected


# ---------------------------------------------------------------------------
# PROB_TO_APPROVAL values
# ---------------------------------------------------------------------------

def test_prob_approval_phase1_is_roughly_7pct():
    p = PROB_TO_APPROVAL["Phase 1"]
    assert 0.05 < p < 0.12, f"Phase 1 prob {p} outside expected 5–12%"


def test_prob_approval_phase3_is_roughly_49pct():
    p = PROB_TO_APPROVAL["Phase 3"]
    assert 0.40 < p < 0.60, f"Phase 3 prob {p} outside expected 40–60%"


def test_prob_approval_approved_is_one():
    assert PROB_TO_APPROVAL["Approved"] == 1.0


def test_prob_ordering():
    assert PROB_TO_APPROVAL["Phase 1"] < PROB_TO_APPROVAL["Phase 2"]
    assert PROB_TO_APPROVAL["Phase 2"] < PROB_TO_APPROVAL["Phase 3"]
    assert PROB_TO_APPROVAL["Phase 3"] < PROB_TO_APPROVAL["NDA/BLA"]
    assert PROB_TO_APPROVAL["NDA/BLA"] < PROB_TO_APPROVAL["Approved"]


# ---------------------------------------------------------------------------
# enrich_trials
# ---------------------------------------------------------------------------

def _sample_df():
    return pd.DataFrame([
        {
            "nct_id": "NCT001", "title": "Drug A Phase 3 Trial",
            "phase": "Phase 3", "status": "RECRUITING",
            "condition": "Cancer", "enrollment": 300,
            "start_date": "2023-01-01",
            "primary_completion_date": "2027-06-01",
            "sponsor": "Sponsor A",
        },
        {
            "nct_id": "NCT002", "title": "Drug B Phase 1 Trial",
            "phase": "Phase 1", "status": "COMPLETED",
            "condition": "Diabetes", "enrollment": 50,
            "start_date": "2021-01-01",
            "primary_completion_date": "2022-06-01",
            "sponsor": "Sponsor B",
        },
    ])


def test_enrich_adds_expected_columns():
    enriched = enrich_trials(_sample_df())
    for col in ("phase_clean", "status_clean", "is_active", "prob_approval", "days_to_primary"):
        assert col in enriched.columns, f"Missing column: {col}"


def test_enrich_active_flag():
    enriched = enrich_trials(_sample_df())
    assert enriched.loc[enriched["nct_id"] == "NCT001", "is_active"].iloc[0] == True
    assert enriched.loc[enriched["nct_id"] == "NCT002", "is_active"].iloc[0] == False


def test_enrich_prob_approval_phase3():
    enriched = enrich_trials(_sample_df())
    p = enriched.loc[enriched["nct_id"] == "NCT001", "prob_approval"].iloc[0]
    assert abs(p - PROB_TO_APPROVAL["Phase 3"]) < 1e-9


def test_enrich_empty_df():
    result = enrich_trials(pd.DataFrame())
    assert result.empty


# ---------------------------------------------------------------------------
# upcoming_catalysts
# ---------------------------------------------------------------------------

def test_upcoming_catalysts_filters_correctly():
    enriched = enrich_trials(_sample_df())
    cats = upcoming_catalysts(enriched, within_days=365 * 5)
    # NCT001 completion is in 2027 (~400 days away) — should be included
    assert len(cats) >= 1
    # NCT002 completion was in 2022 (past) — should be excluded
    assert "NCT002" not in cats["nct_id"].values


def test_pipeline_summary_counts():
    summary = pipeline_summary(_sample_df())
    assert summary["total"] == 2
    assert summary["active"] == 1
    assert summary["phase3_plus"] == 1
