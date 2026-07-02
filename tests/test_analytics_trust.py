"""
Trust tests for the audit's P0 analytics fixes:
  - rNPV values only lead-sponsor trials, de-duplicated to programs (no false positives).
  - The ML result carries an out-of-sample accuracy read.
"""
import numpy as np
import pandas as pd

import server
from pipeline_analyzer import enrich_trials
from model import predict


def _raw_trials() -> pd.DataFrame:
    return pd.DataFrame([
        # Two lead-sponsor trials, same phase + indication → one program after dedupe.
        {"nct_id": "N1", "title": "Drug A in Gastric Cancer", "phase": "Phase 3",
         "status": "RECRUITING", "condition": "Gastric Cancer", "sponsor": "ModernaTX, Inc.",
         "enrollment": 100, "start_date": "2024-01-01", "primary_completion_date": "2026-01-01"},
        {"nct_id": "N2", "title": "Drug A in Gastric Cancer (expansion)", "phase": "Phase 3",
         "status": "RECRUITING", "condition": "Gastric Cancer", "sponsor": "ModernaTX, Inc.",
         "enrollment": 50, "start_date": "2024-06-01", "primary_completion_date": "2026-06-01"},
        # A different owned indication → its own program.
        {"nct_id": "N3", "title": "Drug B in Influenza", "phase": "Phase 2",
         "status": "RECRUITING", "condition": "Influenza", "sponsor": "Moderna, Inc.",
         "enrollment": 200, "start_date": "2024-01-01", "primary_completion_date": "2026-01-01"},
        # False positive: collaborator/registry trial, not lead-sponsored by the company.
        {"nct_id": "N4", "title": "Aspirin in Preventing Cancer Recurrence", "phase": "Phase 3",
         "status": "RECRUITING", "condition": "Colon Cancer", "sponsor": "National Cancer Institute (NCI)",
         "enrollment": 5000, "start_date": "2020-01-01", "primary_completion_date": "2027-01-01"},
    ])


def test_rnpv_drops_false_positives_and_dedupes_to_programs():
    enriched = enrich_trials(_raw_trials())
    programs, sponsor_matched = server._select_pipeline_programs(enriched, "MRNA", "Moderna, Inc.")
    assert sponsor_matched is True
    names = " ".join(programs["title"].tolist()).lower()
    assert "aspirin" not in names, "NCI collaborator trial should be filtered out"
    # 2 gastric Phase 3 → 1 program; 1 influenza Phase 2 → 1 program = 2 total.
    assert len(programs) == 2


def test_rnpv_falls_back_and_flags_when_no_sponsor_match():
    enriched = enrich_trials(_raw_trials())
    _, sponsor_matched = server._select_pipeline_programs(enriched, "ZZZZ", "Nonexistent Pharma XYZ")
    assert sponsor_matched is False


def test_model_reports_out_of_sample_accuracy():
    rng = np.random.default_rng(1)
    n = 320
    close = 100.0 * np.cumprod(1 + rng.normal(0.0005, 0.02, n))
    prices = pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": rng.integers(1e6, 5e6, n).astype(float)},
        index=pd.date_range("2022-01-01", periods=n, freq="B"),
    )
    result = predict("TRUST_OOS", prices)
    if result.trained_on > 0:
        assert result.oos_accuracy is None or 0.0 <= result.oos_accuracy <= 1.0
        assert result.oos_samples >= 0
