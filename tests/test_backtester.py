"""Trust tests for backtester.py — the audit flagged 0-trade 'alpha' as misleading."""
import numpy as np
import pandas as pd

from backtester import run_backtest


def _flat_prices(n: int = 80, price: float = 100.0) -> pd.DataFrame:
    """Constant price series → no RSI/MACD signal ever fires → zero trades."""
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": price, "High": price, "Low": price, "Close": price, "Volume": 1_000_000.0},
        index=idx,
    )


def test_no_trades_yields_null_alpha_not_fake_outperformance():
    """A strategy that never trades must not report alpha vs buy-and-hold."""
    result = run_backtest(_flat_prices())
    assert result.metrics["n_trades"] == 0
    assert result.metrics["alpha_pct"] is None
    assert "no trades" in result.metrics["note"].lower()


def test_metrics_flag_in_sample():
    result = run_backtest(_flat_prices())
    assert result.metrics["in_sample"] is True


def test_trading_run_reports_numeric_alpha():
    """When the strategy does trade, alpha is a number and an in-sample note is present."""
    rng = np.random.default_rng(7)
    n = 400
    close = 100.0 * np.cumprod(1 + rng.normal(0.0, 0.03, n))
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    prices = pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": rng.integers(1e6, 5e6, n).astype(float)},
        index=idx,
    )
    result = run_backtest(prices)
    if result.metrics["n_trades"] > 0:
        assert isinstance(result.metrics["alpha_pct"], float)
        assert "in-sample" in result.metrics["note"].lower()
