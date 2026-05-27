"""
rnpv_calculator.py — Risk-adjusted Net Present Value (rNPV) model for biotech pipelines.

Methodology
-----------
For each pipeline asset:
    peak_sales_estimate  × probability_of_approval × NPV_factor × margin

NPV_factor = sum of discounted annual cash flows over patent life after approval,
             approximated as an annuity using a constant discount rate.

The result is summed across all pipeline assets to get a total pipeline rNPV.
This is a simplified illustrative model; adjust assumptions per company.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from pipeline_analyzer import PROB_TO_APPROVAL, _normalise_phase

# ---------------------------------------------------------------------------
# Default assumptions  (easily overridable via AssetAssumptions)
# ---------------------------------------------------------------------------
DEFAULT_DISCOUNT_RATE    = 0.10   # 10% WACC
DEFAULT_PATENT_LIFE_YRS  = 12     # years of exclusivity post-approval
DEFAULT_OPERATING_MARGIN = 0.35   # 35% operating margin on peak sales
DEFAULT_PEAK_SALES_USD   = 500e6  # $500M peak annual sales (mid-sized indication)

# Rough years-to-market by current phase (used when no explicit date given)
YEARS_TO_MARKET: dict[str, float] = {
    "Phase 1":  7.0,
    "Phase 2":  5.0,
    "Phase 3":  2.5,
    "NDA/BLA":  1.0,
    "Approved": 0.0,
    "Other":    8.0,
}


@dataclass
class AssetAssumptions:
    """Per-asset assumptions for the rNPV model."""
    peak_sales:       float = DEFAULT_PEAK_SALES_USD
    discount_rate:    float = DEFAULT_DISCOUNT_RATE
    patent_life_yrs:  int   = DEFAULT_PATENT_LIFE_YRS
    op_margin:        float = DEFAULT_OPERATING_MARGIN
    years_to_market:  Optional[float] = None   # override auto-estimate if set
    royalty_rate:     float = 0.0              # licensor royalty if partnered
    # Cost of development (negative NPV component)
    dev_cost:         float = 200e6            # $200M remaining development cost
    dev_cost_years:   int   = 3                # years over which dev cost is spent


@dataclass
class AssetValuation:
    """Output of the rNPV model for a single asset."""
    name:             str
    phase:            str
    prob_approval:    float
    peak_sales:       float
    undiscounted_npv: float     # NPV assuming 100% success
    rnpv:             float     # risk-adjusted NPV
    dev_cost_pv:      float     # PV of remaining development costs
    net_rnpv:         float     # rnpv − dev_cost_pv


def asset_rnpv(
    name:        str,
    phase:       str,
    assumptions: Optional[AssetAssumptions] = None,
) -> AssetValuation:
    """
    Compute rNPV for a single pipeline asset.

    Parameters
    ----------
    name        : human-readable asset / programme name
    phase       : raw phase string (e.g. "Phase 2", "PHASE3")
    assumptions : AssetAssumptions (defaults used if None)
    """
    a = assumptions or AssetAssumptions()
    phase_clean = _normalise_phase(phase)
    p_approval  = PROB_TO_APPROVAL.get(phase_clean, 0.0)
    ttm         = a.years_to_market if a.years_to_market is not None else YEARS_TO_MARKET.get(phase_clean, 8.0)

    # Annuity NPV of operating cash flows over patent life, discounted to today
    # First commercial year is (ttm) years away; last is (ttm + patent_life - 1)
    r = a.discount_rate
    annuity_pv = sum(
        a.peak_sales * a.op_margin / (1 + r) ** (ttm + yr)
        for yr in range(a.patent_life_yrs)
    ) * (1 - a.royalty_rate)

    # PV of development costs  (simple straight-line spend over dev_cost_years)
    dev_pv = sum(
        (a.dev_cost / a.dev_cost_years) / (1 + r) ** yr
        for yr in range(1, a.dev_cost_years + 1)
    )

    rnpv     = p_approval * annuity_pv
    net_rnpv = rnpv - dev_pv

    return AssetValuation(
        name             = name,
        phase            = phase_clean,
        prob_approval    = p_approval,
        peak_sales       = a.peak_sales,
        undiscounted_npv = annuity_pv,
        rnpv             = rnpv,
        dev_cost_pv      = dev_pv,
        net_rnpv         = net_rnpv,
    )


def pipeline_rnpv(
    trials_df: pd.DataFrame,
    default_assumptions: Optional[AssetAssumptions] = None,
) -> tuple[float, pd.DataFrame]:
    """
    Compute aggregate pipeline rNPV from an enriched trials DataFrame.

    Returns
    -------
    (total_net_rnpv, detail_df)
    detail_df columns: name, phase, prob_approval, peak_sales,
                       rnpv, dev_cost_pv, net_rnpv
    """
    if trials_df.empty:
        return 0.0, pd.DataFrame()

    a = default_assumptions or AssetAssumptions()
    rows = []
    for _, row in trials_df.iterrows():
        name  = str(row.get("title", "Unknown"))[:80]
        phase = str(row.get("phase", ""))
        val   = asset_rnpv(name, phase, a)
        rows.append({
            "name":          val.name,
            "phase":         val.phase,
            "prob_approval": val.prob_approval,
            "peak_sales":    val.peak_sales,
            "rnpv":          val.rnpv,
            "dev_cost_pv":   val.dev_cost_pv,
            "net_rnpv":      val.net_rnpv,
        })

    detail = pd.DataFrame(rows).sort_values("net_rnpv", ascending=False).reset_index(drop=True)
    total  = detail["net_rnpv"].sum()
    return total, detail


def scenario_analysis(
    phase:      str,
    peak_sales_range: tuple[float, float, float] = (200e6, 500e6, 1_000e6),
    discount_rates:   tuple[float, float, float] = (0.08, 0.10, 0.12),
) -> pd.DataFrame:
    """
    3×3 scenario grid: bear / base / bull peak sales vs. discount rates.
    Returns DataFrame indexed by discount_rate with columns for each sales scenario.
    """
    labels = ["Bear", "Base", "Bull"]
    rows = []
    for rate in discount_rates:
        row = {"discount_rate": f"{rate*100:.0f}%"}
        for label, sales in zip(labels, peak_sales_range):
            a   = AssetAssumptions(peak_sales=sales, discount_rate=rate)
            val = asset_rnpv("Scenario", phase, a)
            row[f"{label} (${sales/1e6:.0f}M peak)"] = val.net_rnpv
        rows.append(row)
    return pd.DataFrame(rows).set_index("discount_rate")
