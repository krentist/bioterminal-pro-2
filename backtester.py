"""
backtester.py — simple signal-based backtest engine.

Strategy : RSI mean-reversion + MACD momentum combo.
           Long when RSI < 35 AND MACD crosses up.
           Flat (cash) otherwise.
           Equal-weight, fully invested when in position.

Output : equity curve, trade log, performance metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

def compute_signals(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical signal columns to prices DataFrame.

    Added columns:
        rsi, macd_line, macd_signal, bb_upper, bb_lower,
        long_signal, short_signal
    """
    df = prices.copy()
    closes = df["Close"].astype(float)

    # RSI
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)

    # MACD
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    df["macd_line"]   = ema12 - ema26
    df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd_line"] - df["macd_signal"]

    # Bollinger Bands
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_mid"]   = sma20

    # Simple long signal: RSI oversold AND MACD histogram turning positive
    rsi_oversold   = df["rsi"] < 35
    macd_cross_up  = (df["macd_hist"] > 0) & (df["macd_hist"].shift(1) <= 0)
    df["long_signal"]  = (rsi_oversold | macd_cross_up).astype(int)

    # Exit signal: RSI overbought OR MACD histogram turning negative
    rsi_overbought = df["rsi"] > 65
    macd_cross_dn  = (df["macd_hist"] < 0) & (df["macd_hist"].shift(1) >= 0)
    df["exit_signal"]  = (rsi_overbought | macd_cross_dn).astype(int)

    return df


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    equity_curve:   pd.Series          # portfolio value over time
    trade_log:      pd.DataFrame       # entry/exit details
    metrics:        dict               # performance statistics
    signals_df:     pd.DataFrame       # full signals DataFrame


def run_backtest(
    prices:          pd.DataFrame,
    initial_capital: float = 100_000.0,
    commission_pct:  float = 0.001,    # 0.1% per side
    hold_days:       int   = 20,       # max hold period if no exit signal
) -> BacktestResult:
    """
    Run the RSI+MACD strategy on historical OHLCV data.

    Parameters
    ----------
    prices          : OHLCV DataFrame with DatetimeIndex
    initial_capital : starting capital in strategy currency
    commission_pct  : one-way commission rate
    hold_days       : force-close after this many days if no exit signal
    """
    if prices.empty or len(prices) < 50:
        empty = BacktestResult(
            equity_curve=pd.Series(dtype=float),
            trade_log=pd.DataFrame(),
            metrics={},
            signals_df=pd.DataFrame(),
        )
        return empty

    sig_df = compute_signals(prices)
    closes = sig_df["Close"].astype(float)

    cash      = initial_capital
    position  = 0.0       # shares held
    entry_px  = 0.0
    entry_idx = -1
    trades    = []
    equity    = []

    for i, (dt, row) in enumerate(sig_df.iterrows()):
        px = float(row["Close"])

        # Mark-to-market
        portfolio_val = cash + position * px
        equity.append({"date": dt, "value": portfolio_val})

        if pd.isna(row.get("rsi")) or pd.isna(row.get("macd_hist")):
            continue

        # Entry
        if position == 0 and row["long_signal"] == 1:
            shares   = cash / px
            cost     = shares * px * (1 + commission_pct)
            if cost <= cash:
                position  = shares
                cash     -= cost
                entry_px  = px
                entry_idx = i

        # Exit
        elif position > 0:
            force_exit = (i - entry_idx) >= hold_days
            if row["exit_signal"] == 1 or force_exit:
                proceeds = position * px * (1 - commission_pct)
                pnl      = proceeds - (position * entry_px)
                trades.append({
                    "entry_date":  sig_df.index[entry_idx],
                    "exit_date":   dt,
                    "entry_price": entry_px,
                    "exit_price":  px,
                    "shares":      position,
                    "pnl":         pnl,
                    "pnl_pct":     pnl / (position * entry_px) * 100,
                    "hold_days":   i - entry_idx,
                    "exit_reason": "signal" if not force_exit else "max_hold",
                })
                cash     += proceeds
                position  = 0.0
                entry_px  = 0.0
                entry_idx = -1

    equity_series = pd.Series(
        [e["value"] for e in equity],
        index=[e["date"] for e in equity],
        name="portfolio_value",
    )
    trade_df = pd.DataFrame(trades)
    metrics  = _calc_metrics(equity_series, trade_df, initial_capital, closes)

    return BacktestResult(
        equity_curve=equity_series,
        trade_log=trade_df,
        metrics=metrics,
        signals_df=sig_df,
    )


def _calc_metrics(
    equity:  pd.Series,
    trades:  pd.DataFrame,
    initial: float,
    closes:  pd.Series,
) -> dict:
    if equity.empty:
        return {}

    total_return = (equity.iloc[-1] / initial - 1) * 100
    days         = (equity.index[-1] - equity.index[0]).days or 1
    cagr         = ((equity.iloc[-1] / initial) ** (365 / days) - 1) * 100

    daily_ret    = equity.pct_change().dropna()
    sharpe       = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() else 0.0

    rolling_max  = equity.cummax()
    drawdown     = (equity - rolling_max) / rolling_max
    max_dd       = drawdown.min() * 100

    # Buy-and-hold benchmark
    bh_return    = (closes.iloc[-1] / closes.iloc[0] - 1) * 100 if len(closes) > 1 else 0.0

    win_rate, avg_win, avg_loss = _trade_stats(trades)

    # A strategy that never opened a position has no performance to compare against
    # buy-and-hold. Reporting "alpha = 0% − buy&hold%" in that case implies the
    # strategy actively outperformed when it merely sat in cash — so alpha is null.
    no_trades = trades.empty
    if no_trades:
        note = ("Strategy generated no trades in this period — it stayed in cash. "
                "Strategy return is 0% and alpha versus buy-and-hold is not meaningful.")
    else:
        note = ("In-sample results on this single ticker; the strategy is fit and measured "
                "on the same history, so returns are not out-of-sample. Commissions of 0.1% "
                "per side are modelled; slippage and market impact are not.")

    return {
        "total_return_pct": round(total_return, 2),
        "cagr_pct":         round(cagr, 2),
        "sharpe_ratio":     round(float(sharpe), 3),
        "max_drawdown_pct": round(float(max_dd), 2),
        "bh_return_pct":    round(bh_return, 2),
        "alpha_pct":        None if no_trades else round(total_return - bh_return, 2),
        "n_trades":         len(trades),
        "win_rate_pct":     round(win_rate * 100, 1),
        "avg_win_pct":      round(avg_win, 2),
        "avg_loss_pct":     round(avg_loss, 2),
        "in_sample":        True,
        "note":             note,
    }


def _trade_stats(trades: pd.DataFrame) -> tuple[float, float, float]:
    if trades.empty:
        return 0.0, 0.0, 0.0
    wins  = trades[trades["pnl"] > 0]
    losses= trades[trades["pnl"] <= 0]
    wr    = len(wins) / len(trades) if len(trades) else 0.0
    aw    = wins["pnl_pct"].mean()   if not wins.empty   else 0.0
    al    = losses["pnl_pct"].mean() if not losses.empty else 0.0
    return wr, float(aw), float(al)
