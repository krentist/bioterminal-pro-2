"""
model.py — ML prediction engine for BioTerminal Pro.

Model
-----
RandomForestClassifier trained on rolling windows of feature history.
Target  : binary — whether the stock outperforms its sector benchmark over
          the next 20 trading days (1 = outperform, 0 = underperform).
          Falls back to absolute-return > 0 when no sector benchmark is supplied.
Features: price-only momentum, trend, volatility, and volume signals.
          Fundamentals are intentionally excluded to avoid look-ahead bias:
          using today's P/E for historical training windows contaminates the
          feature set with future information.

Usage
-----
    result = predict(ticker, prices_df, sector_closes=sector_series)
    result.signal        # "BULLISH" | "BEARISH" | "NEUTRAL"
    result.confidence    # 0.0 – 1.0
    result.feature_df    # DataFrame of feature importances
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings("ignore")

_MODEL_CACHE: dict[str, object] = {}
_MODEL_CACHE_LOCK = Lock()
_MODEL_CACHE_TTL = 600  # 10 minutes

# Sentinel: a thread has claimed this ticker's training slot.
_LOADING = object()


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a single-row feature DataFrame from price history alone.
    Requires at least 60 trading days.
    """
    if prices.empty or len(prices) < 60:
        return pd.DataFrame()

    df = prices.copy()
    closes = df["Close"].astype(float)
    volume = df["Volume"].astype(float).replace(0, np.nan)

    ret = closes.pct_change()
    features: dict[str, float] = {
        "ret_1d":  ret.iloc[-1],
        "ret_5d":  closes.pct_change(5).iloc[-1],
        "ret_20d": closes.pct_change(20).iloc[-1],
        "ret_60d": closes.pct_change(60).iloc[-1],
    }

    sma20 = closes.rolling(20).mean()
    sma50 = closes.rolling(50).mean() if len(closes) >= 50 else pd.Series([np.nan] * len(closes))
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()

    features["price_vs_sma20"] = (closes.iloc[-1] / sma20.iloc[-1] - 1) if sma20.iloc[-1] else np.nan
    features["sma20_vs_sma50"] = (sma20.iloc[-1] / sma50.iloc[-1] - 1) if (not pd.isna(sma50.iloc[-1]) and sma50.iloc[-1]) else np.nan
    features["macd_line"]      = (ema12 - ema26).iloc[-1]
    features["macd_signal"]    = (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1]
    features["rsi_14"]         = _rsi(closes, 14)
    features["vol_20d"]        = ret.rolling(20).std().iloc[-1] * np.sqrt(252)
    features["vol_ratio"]      = (
        ret.rolling(5).std().iloc[-1] / ret.rolling(20).std().iloc[-1]
        if ret.rolling(20).std().iloc[-1] else np.nan
    )

    vol_ma20 = volume.rolling(20).mean().iloc[-1]
    features["vol_ratio_20d"] = volume.iloc[-1] / vol_ma20 if vol_ma20 else np.nan

    bb_mid = sma20.iloc[-1]
    bb_std = closes.rolling(20).std().iloc[-1]
    features["bb_position"] = (closes.iloc[-1] - bb_mid) / (2 * bb_std) if bb_std else np.nan

    return pd.DataFrame([features])


def build_training_dataset(
    prices: pd.DataFrame,
    lookahead: int = 20,
    sector_closes: Optional[pd.Series] = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build a rolling-window feature matrix and binary target for training.

    Each row = features computed at day t.
    Target = 1 if stock outperforms sector_closes over [t+1 : t+lookahead],
             or 1 if absolute return > 0 when sector_closes is None.

    sector_closes must be pre-aligned to prices.index (same length, same order).
    """
    if prices.empty or len(prices) < 120:
        return pd.DataFrame(), pd.Series(dtype=int)

    closes = prices["Close"].astype(float)
    use_sector = (
        sector_closes is not None
        and len(sector_closes) == len(prices)
        and not sector_closes.isna().all()
    )
    rows, targets = [], []

    for i in range(60, len(prices) - lookahead):
        window = prices.iloc[:i]
        feats  = build_features(window)
        if feats.empty:
            continue

        fwd_ret = closes.iloc[i + lookahead] / closes.iloc[i] - 1

        if use_sector:
            sec_fwd = sector_closes.iloc[i + lookahead] / sector_closes.iloc[i] - 1
            label   = 1 if fwd_ret > float(sec_fwd) else 0
        else:
            label = 1 if fwd_ret > 0 else 0

        rows.append(feats.iloc[0])
        targets.append(label)

    if not rows:
        return pd.DataFrame(), pd.Series(dtype=int)
    return pd.DataFrame(rows).fillna(0), pd.Series(targets, name="target")


# ---------------------------------------------------------------------------
# Model training & prediction
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    signal:      str          # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence:  float        # 0–1
    bull_prob:   float        # P(outperform)
    bear_prob:   float        # P(underperform)
    feature_df:  pd.DataFrame
    trained_on:  int          # number of training samples
    oos_accuracy: Optional[float] = None  # walk-forward hold-out accuracy (None if not evaluated)
    oos_samples:  int = 0                  # size of the hold-out test window


def predict(
    ticker:        str,
    prices:        pd.DataFrame,
    lookahead:     int = 20,
    n_estimators:  int = 200,
    sector_closes: Optional[pd.Series] = None,
) -> PredictionResult:
    """
    Train a RandomForest on historical price-only feature/target pairs, then predict
    the current signal. Results are cached per ticker for 10 minutes.

    sector_closes — optional benchmark series (e.g. XBI for US, 2800.HK for HK)
    aligned to the same DatetimeIndex as prices. When supplied the target becomes
    sector-relative outperformance; otherwise falls back to absolute return > 0.
    """
    now = time.monotonic()

    # Double-checked locking with a sentinel to prevent thundering herd:
    # only the first thread to see a missing/expired entry trains the model.
    with _MODEL_CACHE_LOCK:
        entry = _MODEL_CACHE.get(ticker)
        if entry is _LOADING:
            # Another thread is already training — return neutral immediately.
            return _neutral()
        if entry is not None:
            cached_result, ts = entry  # type: ignore[misc]
            if now - ts < _MODEL_CACHE_TTL:
                return cached_result
        # Claim the slot before releasing the lock.
        _MODEL_CACHE[ticker] = _LOADING

    result = _train_and_predict(ticker, prices, lookahead, n_estimators, sector_closes)

    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[ticker] = (result, time.monotonic())

    return result


def _neutral() -> PredictionResult:
    return PredictionResult(
        signal="NEUTRAL", confidence=0.0,
        bull_prob=0.5, bear_prob=0.5,
        feature_df=pd.DataFrame(), trained_on=0,
    )


def _train_and_predict(
    ticker:        str,
    prices:        pd.DataFrame,
    lookahead:     int,
    n_estimators:  int,
    sector_closes: Optional[pd.Series],
) -> PredictionResult:
    X_train, y_train = build_training_dataset(prices, lookahead, sector_closes)

    if X_train.empty or len(y_train) < 30:
        return _neutral()

    # RandomForest is scale-invariant — StandardScaler is not applied.
    X_arr = X_train.fillna(0).values

    def _make_clf() -> RandomForestClassifier:
        return RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )

    # Walk-forward hold-out: training rows are in chronological order, so train on
    # the earlier 80% and measure accuracy on the most recent 20%. This is the only
    # honest read on whether the signal has any out-of-sample skill; the value is
    # surfaced to the UI so the score is never presented as validated when it isn't.
    oos_accuracy: Optional[float] = None
    oos_samples = 0
    n = len(y_train)
    if n >= 50:
        split = int(n * 0.8)
        y_tr = y_train.iloc[:split]
        y_te = y_train.iloc[split:]
        if y_tr.nunique() > 1 and len(y_te) > 0:
            val_clf = _make_clf()
            val_clf.fit(X_arr[:split], y_tr)
            oos_accuracy = round(float((val_clf.predict(X_arr[split:]) == y_te.values).mean()), 4)
            oos_samples = int(len(y_te))

    clf = _make_clf()
    clf.fit(X_arr, y_train)

    current_feats = build_features(prices)
    if current_feats.empty:
        return PredictionResult(
            signal="NEUTRAL", confidence=0.0,
            bull_prob=0.5, bear_prob=0.5,
            feature_df=pd.DataFrame(), trained_on=len(y_train),
        )

    X_pred = current_feats.reindex(columns=X_train.columns, fill_value=0).fillna(0).values
    proba  = clf.predict_proba(X_pred)[0]

    classes   = list(clf.classes_)
    bull_prob = proba[classes.index(1)] if 1 in classes else 0.5
    bear_prob = proba[classes.index(0)] if 0 in classes else 0.5
    confidence = abs(bull_prob - 0.5) * 2

    if bull_prob >= 0.60:
        signal = "BULLISH"
    elif bear_prob >= 0.60:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    feat_df = pd.DataFrame({
        "feature":    X_train.columns,
        "importance": clf.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    return PredictionResult(
        signal=signal,
        confidence=round(confidence, 4),
        bull_prob=round(bull_prob, 4),
        bear_prob=round(bear_prob, 4),
        feature_df=feat_df,
        trained_on=len(y_train),
        oos_accuracy=oos_accuracy,
        oos_samples=oos_samples,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rsi(series: pd.Series, window: int = 14) -> float:
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(window).mean()
    loss  = (-delta.clip(upper=0)).rolling(window).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1]) if not rsi.empty else np.nan
