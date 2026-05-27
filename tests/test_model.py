"""Unit tests for model.py."""
import numpy as np
import pandas as pd
import pytest

from model import build_features, build_training_dataset, predict, PredictionResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_prices(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame with n trading days."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0005, 0.02, n)
    close = 100.0 * np.cumprod(1 + ret)
    return pd.DataFrame(
        {
            "Open":   close * (1 - rng.uniform(0, 0.005, n)),
            "High":   close * (1 + rng.uniform(0, 0.01, n)),
            "Low":    close * (1 - rng.uniform(0, 0.01, n)),
            "Close":  close,
            "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
        },
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
    )


_SAMPLE_FUNDS = {
    "pe_ratio": 25.0, "pb_ratio": 3.0, "ps_ratio": 5.0,
    "ev_revenue": 6.0, "beta": 1.2, "profit_margin": 0.15,
    "revenue_growth": 0.20,
}


# ---------------------------------------------------------------------------
# build_features
# ---------------------------------------------------------------------------

def test_build_features_returns_single_row():
    prices = _make_prices(200)
    feats = build_features(prices, _SAMPLE_FUNDS)
    assert len(feats) == 1


def test_build_features_has_expected_columns():
    prices = _make_prices(200)
    feats = build_features(prices, _SAMPLE_FUNDS)
    expected = {"ret_1d", "ret_5d", "ret_20d", "ret_60d", "rsi_14",
                "macd_line", "vol_20d", "bb_position", "pe_ratio"}
    assert expected.issubset(set(feats.columns))


def test_build_features_requires_60_days():
    prices = _make_prices(59)   # one day short
    feats = build_features(prices, {})
    assert feats.empty


def test_build_features_with_60_days_succeeds():
    prices = _make_prices(60)
    feats = build_features(prices, {})
    assert len(feats) == 1


def test_build_features_no_fundamentals():
    prices = _make_prices(200)
    feats = build_features(prices, {})
    assert len(feats) == 1  # fundamentals are optional


# ---------------------------------------------------------------------------
# build_training_dataset
# ---------------------------------------------------------------------------

def test_training_dataset_requires_120_days():
    prices = _make_prices(119)
    X, y = build_training_dataset(prices, {})
    assert X.empty and y.empty


def test_training_dataset_shape_consistency():
    prices = _make_prices(300)
    X, y = build_training_dataset(prices, _SAMPLE_FUNDS)
    assert len(X) == len(y)
    assert len(X) > 0


def test_training_target_is_binary():
    prices = _make_prices(300)
    _, y = build_training_dataset(prices, _SAMPLE_FUNDS)
    assert set(y.unique()).issubset({0, 1})


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------

def test_predict_returns_prediction_result():
    prices = _make_prices(300)
    result = predict("TEST", prices, _SAMPLE_FUNDS)
    assert isinstance(result, PredictionResult)


def test_predict_signal_is_valid():
    prices = _make_prices(300)
    result = predict("TEST", prices, _SAMPLE_FUNDS)
    assert result.signal in ("BULLISH", "BEARISH", "NEUTRAL")


def test_predict_probabilities_sum_to_one():
    prices = _make_prices(300)
    result = predict("TEST", prices, _SAMPLE_FUNDS)
    assert abs(result.bull_prob + result.bear_prob - 1.0) < 1e-6


def test_predict_confidence_in_range():
    prices = _make_prices(300)
    result = predict("TEST", prices, _SAMPLE_FUNDS)
    assert 0.0 <= result.confidence <= 1.0


def test_predict_short_history_returns_neutral():
    prices = _make_prices(100)  # too short for training (needs ≥ 120 + lookahead)
    result = predict("TEST", prices, {})
    assert result.signal == "NEUTRAL"
    assert result.trained_on == 0


def test_predict_feature_df_has_importances():
    prices = _make_prices(300)
    result = predict("TEST", prices, _SAMPLE_FUNDS)
    if not result.feature_df.empty:
        assert "feature" in result.feature_df.columns
        assert "importance" in result.feature_df.columns
        assert (result.feature_df["importance"] >= 0).all()
