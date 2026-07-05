"""Unit tests for the cash-runway computation (server._compute_runway).

Burn is sourced from the annual cash-flow statement, so these patch the
statement helper rather than hitting the network.
"""
import server


def _patch_cashflow(monkeypatch, fcf, ocf):
    monkeypatch.setattr(
        server.df_mod, "get_annual_cashflow",
        lambda t: {"free_cash_flow": fcf, "operating_cash_flow": ocf},
    )


def test_runway_burns_cash_uses_statement_fcf(monkeypatch):
    _patch_cashflow(monkeypatch, -2_000_000_000.0, -1_800_000_000.0)
    r = server._compute_runway("MRNA", {"totalCash": 5_000_000_000})
    assert r["cashGenerating"] is False
    assert r["annualBurn"] == 2_000_000_000.0
    assert r["runwayYears"] == 2.5
    assert r["burnBasis"] == "freeCashflow"


def test_runway_cash_generating_has_no_runway(monkeypatch):
    _patch_cashflow(monkeypatch, 9_000_000_000.0, 10_000_000_000.0)
    r = server._compute_runway("GILD", {"totalCash": 9_000_000_000})
    assert r["cashGenerating"] is True
    assert r["annualBurn"] is None
    assert r["runwayYears"] is None


def test_runway_falls_back_to_operating_cash_flow(monkeypatch):
    _patch_cashflow(monkeypatch, None, -100_000_000.0)
    r = server._compute_runway("X", {"totalCash": 200_000_000})
    assert r["burnBasis"] == "operatingCashflow"
    assert r["runwayYears"] == 2.0


def test_runway_ignores_unreliable_info_scalar_when_statement_present(monkeypatch):
    # Statement says -$2B; the stray .info scalar says -$20M. Statement must win.
    _patch_cashflow(monkeypatch, -2_000_000_000.0, None)
    r = server._compute_runway("MRNA", {"totalCash": 5_000_000_000, "freeCashflow": -20_000_000})
    assert r["annualBurn"] == 2_000_000_000.0
    assert r["runwayYears"] == 2.5


def test_runway_no_cashflow_data(monkeypatch):
    _patch_cashflow(monkeypatch, None, None)
    r = server._compute_runway("X", {"totalCash": 200_000_000})
    assert r["burnBasis"] is None
    assert r["runwayYears"] is None
    assert r["cashGenerating"] is None
