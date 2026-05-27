"""
model.py — ML prediction engine for BioTerminal Pro.

Model
-----
RandomForestClassifier trained on rolling windows of feature history.
Target  : binary — whether the stock outperforms its sector over the
          next 20 trading days (1 = outperform, 0 = underperform).
Features: momentum, technical, valuation, and quality signals.

Usage
-----
    result = predict(ticker, prices_df, fundamentals_dict)
    result.signal        # "BULLISH" | "BEARISH" | "NEUTRAL"
    result.confidence    # 0.0 – 1.0
    result.feature_df    # DataFrame of current feature values
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_features(prices: pd.DataFrame, fundamentals: dict) -> pd.DataFrame:
    """
    Compute a single-row feature DataFrame from price history + fundamentals.

    Requires at least 60 trading days of price history.
    """
    if prices.empty or len(prices) < 60:
        return pd.DataFrame()

    df = prices.copy()
    closes = df["Close"].astype(float)
    volume = df["Volume"].astype(float).replace(0, np.nan)

    # --- Momentum ---
    ret = closes.pct_change()
    features = {
        "ret_1d":   ret.iloc[-1],
        "ret_5d":   closes.pct_change(5).iloc[-1],
        "ret_20d":  closes.pct_change(20).iloc[-1],
        "ret_60d":  closes.pct_change(60).iloc[-1],
    }

    # --- Trend ---
    sma20  = closes.rolling(20).mean()
    sma50  = closes.rolling(50).mean() if len(closes) >= 50 else pd.Series([np.nan]*len(closes))
    ema12  = closes.ewm(span=12, adjust=False).mean()
    ema26  = closes.ewm(span=26, adjust=False).mean()

    features["price_vs_sma20"]  = (closes.iloc[-1] / sma20.iloc[-1] - 1) if sma20.iloc[-1] else np.nan
    features["sma20_vs_sma50"]  = (sma20.iloc[-1] / sma50.iloc[-1] - 1)  if (not pd.isna(sma50.iloc[-1]) and sma50.iloc[-1]) else np.nan
    features["macd_line"]       = (ema12 - ema26).iloc[-1]
    features["macd_signal"]     = (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1]

    # --- RSI ---
    features["rsi_14"] = _rsi(closes, 14)

    # --- Volatility ---
    features["vol_20d"] = ret.rolling(20).std().iloc[-1] * np.sqrt(252)
    features["vol_ratio"] = (
        ret.rolling(5).std().iloc[-1] / ret.rolling(20).std().iloc[-1]
        if ret.rolling(20).std().iloc[-1] else np.nan
    )

    # --- Volume ---
    vol_ma20 = volume.rolling(20).mean().iloc[-1]
    features["vol_ratio_20d"] = volume.iloc[-1] / vol_ma20 if vol_ma20 else np.nan

    # --- Bollinger Band position ---
    bb_mid = sma20.iloc[-1]
    bb_std = closes.rolling(20).std().iloc[-1]
    features["bb_position"] = (closes.iloc[-1] - bb_mid) / (2 * bb_std) if bb_std else np.nan

    # --- Fundamentals ---
    features["pe_ratio"]     = _clip(fundamentals.get("pe_ratio"), 0, 200)
    features["pb_ratio"]     = _clip(fundamentals.get("pb_ratio"), 0, 50)
    features["ps_ratio"]     = _clip(fundamentals.get("ps_ratio"), 0, 100)
    features["ev_revenue"]   = _clip(fundamentals.get("ev_revenue"), 0, 200)
    features["beta"]         = _clip(fundamentals.get("beta"), -3, 5)
    features["profit_margin"]= _clip(fundamentals.get("profit_margin"), -2, 1)
    features["revenue_growth"]= _clip(fundamentals.get("revenue_growth"), -1, 5)

    return pd.DataFrame([features])


def build_training_dataset(prices: pd.DataFrame, fundamentals: dict, lookahead: int = 20) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build a rolling-window feature matrix and binary target for training.
    Each row = features computed at day t; target = 1 if return[t+1:t+lookahead] > 0.
    """
    if prices.empty or len(prices) < 120:
        return pd.DataFrame(), pd.Series(dtype=int)

    closes = prices["Close"].astype(float)
    rows, targets = [], []

    for i in range(60, len(prices) - lookahead):
        window = prices.iloc[:i]
        feats  = build_features(window, fundamentals)
        if feats.empty:
            continue
        fwd_ret = closes.iloc[i + lookahead] / closes.iloc[i] - 1
        rows.append(feats.iloc[0])
        targets.append(1 if fwd_ret > 0 else 0)

    if not rows:
        return pd.DataFrame(), pd.Series(dtype=int)
    return pd.DataFrame(rows).fillna(0), pd.Series(targets, name="target")


# ---------------------------------------------------------------------------
# Model training & prediction
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    signal:      str         # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence:  float       # 0–1
    bull_prob:   float       # P(outperform)
    bear_prob:   float       # P(underperform)
    feature_df:  pd.DataFrame
    trained_on:  int         # number of training samples


def predict(
    ticker:       str,
    prices:       pd.DataFrame,
    fundamentals: dict,
    lookahead:    int = 20,
    n_estimators: int = 200,
) -> PredictionResult:
    """
    Train a RandomForest on historical feature/target pairs, then predict
    the current signal from the most-recent feature vector.
    """
    X_train, y_train = build_training_dataset(prices, fundamentals, lookahead)

    if X_train.empty or len(y_train) < 30:
        return PredictionResult(
            signal="NEUTRAL", confidence=0.0,
            bull_prob=0.5, bear_prob=0.5,
            feature_df=pd.DataFrame(), trained_on=0,
        )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train.fillna(0))

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=6,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_scaled, y_train)

    current_feats = build_features(prices, fundamentals)
    if current_feats.empty:
        return PredictionResult(
            signal="NEUTRAL", confidence=0.0,
            bull_prob=0.5, bear_prob=0.5,
            feature_df=pd.DataFrame(), trained_on=len(y_train),
        )

    # Align columns
    current_feats = current_feats.reindex(columns=X_train.columns, fill_value=0).fillna(0)
    X_pred = scaler.transform(current_feats)
    proba  = clf.predict_proba(X_pred)[0]

    # Map classes to bull/bear; class order from sklearn
    classes    = list(clf.classes_)
    bull_prob  = proba[classes.index(1)] if 1 in classes else 0.5
    bear_prob  = proba[classes.index(0)] if 0 in classes else 0.5
    confidence = abs(bull_prob - 0.5) * 2   # 0 at 50/50, 1 at 100/0

    if bull_prob >= 0.60:
        signal = "BULLISH"
    elif bear_prob >= 0.60:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    # Feature importance table
    importances = clf.feature_importances_
    feat_df = pd.DataFrame({
        "feature":    X_train.columns,
        "importance": importances,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    return PredictionResult(
        signal=signal,
        confidence=round(confidence, 4),
        bull_prob=round(bull_prob, 4),
        bear_prob=round(bear_prob, 4),
        feature_df=feat_df,
        trained_on=len(y_train),
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


def _clip(v, lo, hi):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    return float(np.clip(v, lo, hi))
