"""Unit tests for rnpv_calculator.py."""
import pandas as pd
import pytest

from rnpv_calculator import (
    AssetAssumptions,
    AssetValuation,
    asset_rnpv,
    pipeline_rnpv,
    scenario_analysis,
    DEFAULT_DISCOUNT_RATE,
    DEFAULT_PATENT_LIFE_YRS,
    DEFAULT_PEAK_SALES_USD,
)


# ---------------------------------------------------------------------------
# asset_rnpv
# ---------------------------------------------------------------------------

def test_approved_asset_has_prob_one():
    val = asset_rnpv("Approved Drug", "Approved")
    assert val.prob_approval == 1.0


def test_phase3_prob_is_roughly_49pct():
    val = asset_rnpv("Phase3 Drug", "Phase 3")
    assert 0.40 < val.prob_approval < 0.60


def test_phase1_rnpv_less_than_phase3():
    v1 = asset_rnpv("P1", "Phase 1")
    v3 = asset_rnpv("P3", "Phase 3")
    assert v1.rnpv < v3.rnpv


def test_higher_peak_sales_gives_higher_rnpv():
    a_low  = AssetAssumptions(peak_sales=200e6)
    a_high = AssetAssumptions(peak_sales=1_000e6)
    v_low  = asset_rnpv("Low", "Phase 3", a_low)
    v_high = asset_rnpv("High", "Phase 3", a_high)
    assert v_high.rnpv > v_low.rnpv


def test_higher_discount_rate_gives_lower_rnpv():
    a_low  = AssetAssumptions(discount_rate=0.08)
    a_high = AssetAssumptions(discount_rate=0.15)
    v_low  = asset_rnpv("LowDiscount", "Phase 3", a_low)
    v_high = asset_rnpv("HighDiscount", "Phase 3", a_high)
    assert v_low.rnpv > v_high.rnpv


def test_net_rnpv_equals_rnpv_minus_dev_cost():
    val = asset_rnpv("Test", "Phase 2")
    assert abs(val.net_rnpv - (val.rnpv - val.dev_cost_pv)) < 1e-6


def test_returns_asset_valuation_dataclass():
    val = asset_rnpv("Test", "Phase 2")
    assert isinstance(val, AssetValuation)
    assert val.name == "Test"
    assert val.phase == "Phase 2"


# ---------------------------------------------------------------------------
# pipeline_rnpv
# ---------------------------------------------------------------------------

def _trials_df():
    return pd.DataFrame([
        {"title": "Drug A", "phase": "Phase 3"},
        {"title": "Drug B", "phase": "Phase 1"},
    ])


def test_pipeline_rnpv_returns_tuple():
    total, detail = pipeline_rnpv(_trials_df())
    assert isinstance(total, float)
    assert isinstance(detail, pd.DataFrame)


def test_pipeline_rnpv_detail_has_expected_columns():
    _, detail = pipeline_rnpv(_trials_df())
    for col in ("name", "phase", "prob_approval", "rnpv", "net_rnpv"):
        assert col in detail.columns


def test_pipeline_rnpv_total_matches_sum():
    total, detail = pipeline_rnpv(_trials_df())
    assert abs(total - detail["net_rnpv"].sum()) < 1e-6


def test_pipeline_rnpv_empty_df():
    total, detail = pipeline_rnpv(pd.DataFrame())
    assert total == 0.0
    assert detail.empty


# ---------------------------------------------------------------------------
# scenario_analysis
# ---------------------------------------------------------------------------

def test_scenario_analysis_shape():
    df = scenario_analysis("Phase 3")
    assert df.shape == (3, 3), f"Expected 3x3, got {df.shape}"


def test_scenario_analysis_bull_gt_base_gt_bear():
    df = scenario_analysis("Phase 3")
    # Bear sales < Base sales < Bull sales → same ordering for net_rnpv at base discount
    base_row = df.iloc[1]  # middle discount rate
    values = base_row.tolist()
    assert values[0] < values[1] < values[2], "Bull > Base > Bear ordering violated"
