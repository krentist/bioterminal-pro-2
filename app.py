"""
BioTerminal Pro — Multi-region biotech quant dashboard.
Built with Streamlit + Plotly.

Tabs
----
Overview · Technical · Pipeline & Catalysts · Prediction Engine
Peer Comparison · News & Filings · Watchlist · Alpha Radar · Earnings Intelligence
"""
from __future__ import annotations

import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st

warnings.filterwarnings("ignore")

# ── Local modules ────────────────────────────────────────────────────────────
import data_fetcher as df_mod
from exchanges import get_exchange_adapter
from pipeline_analyzer import enrich_trials, phase_breakdown, upcoming_catalysts, pipeline_summary
from rnpv_calculator import pipeline_rnpv, AssetAssumptions
from backtester import run_backtest, compute_signals
from utils import fmt_large, fmt_pct, fmt_ratio, fmt_num, period_to_dates

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BioTerminal Pro",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme CSS ─────────────────────────────────────────────────────────────
DARK_CSS = """
<style>
  /* --- Base --- */
  .stApp, [data-testid="stAppViewContainer"] { background:#09090f; color:#e2e8f0; }
  [data-testid="stSidebar"] { background:#0f0f1a; border-right:1px solid #1e2035; }
  [data-testid="stHeader"]  { background:#09090f; }

  /* --- Metric cards --- */
  .metric-card {
    background:#13131f; border:1px solid #1e2035; border-radius:10px;
    padding:16px 20px; margin-bottom:8px;
  }
  .metric-label { font-size:11px; color:#64748b; text-transform:uppercase;
                  letter-spacing:.08em; margin-bottom:4px; }
  .metric-value { font-size:22px; font-weight:700; color:#e2e8f0; }
  .metric-delta-up   { font-size:13px; color:#22c55e; }
  .metric-delta-down { font-size:13px; color:#ef4444; }

  /* --- Region badge --- */
  .badge-us { background:#1e3a5f; color:#60a5fa;
              padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
  .badge-hk { background:#3b1e1e; color:#f87171;
              padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
  .badge-neutral { background:#1e2535; color:#94a3b8;
                   padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }

  /* --- Signal badges --- */
  .signal-bullish { color:#22c55e; font-weight:700; font-size:18px; }
  .signal-bearish { color:#ef4444; font-weight:700; font-size:18px; }
  .signal-neutral { color:#f59e0b; font-weight:700; font-size:18px; }

  /* --- Risk severity --- */
  .sev-5 { color:#ef4444; } .sev-4 { color:#f97316; }
  .sev-3 { color:#f59e0b; } .sev-2 { color:#84cc16; } .sev-1 { color:#22c55e; }

  /* --- Tables --- */
  .stDataFrame { font-size:13px; }
  thead tr th { background:#13131f !important; color:#94a3b8 !important; }

  /* --- Inputs --- */
  .stTextInput > div > div > input { background:#13131f; border-color:#1e2035;
                                      color:#e2e8f0; }
  .stSelectbox > div > div { background:#13131f; border-color:#1e2035; }
  div[data-baseweb="select"] > div { background:#13131f; }

  /* --- Tabs --- */
  .stTabs [data-baseweb="tab-list"]  { background:#0f0f1a; gap:4px; }
  .stTabs [data-baseweb="tab"]       { background:#13131f; color:#64748b;
                                        border-radius:6px 6px 0 0; padding:8px 16px; }
  .stTabs [aria-selected="true"]     { background:#1e2035 !important; color:#60a5fa !important; }

  /* --- Divider --- */
  hr { border-color:#1e2035; }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# ── Plotly dark template ───────────────────────────────────────────────────────
PLOTLY_THEME = dict(
    template="plotly_dark",
    paper_bgcolor="#09090f",
    plot_bgcolor="#09090f",
    font=dict(family="Inter, sans-serif", color="#e2e8f0"),
    xaxis=dict(gridcolor="#1e2035", zerolinecolor="#1e2035"),
    yaxis=dict(gridcolor="#1e2035", zerolinecolor="#1e2035"),
)


# ── Session state ─────────────────────────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["MRNA", "REGN", "VRTX", "2269.HK", "6160.HK"]


# ── Cached data helpers ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(ticker: str, period: str, interval: str = "1d") -> pd.DataFrame:
    return df_mod.get_price_history(ticker, period=period, interval=interval)


@st.cache_data(ttl=3600, show_spinner=False)
def load_info(ticker: str) -> dict:
    return df_mod.get_company_info(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fundamentals(ticker: str) -> dict:
    return df_mod.get_financial_metrics(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def load_news(ticker: str) -> pd.DataFrame:
    return df_mod.get_news_feed(ticker, limit=30)


@st.cache_data(ttl=3600, show_spinner=False)
def load_pipeline(ticker: str) -> pd.DataFrame:
    return df_mod.get_pipeline_data(ticker)


@st.cache_data(ttl=7200, show_spinner=False)
def load_earnings(ticker: str) -> dict:
    from earnings_analyzer import earnings_summary
    return earnings_summary(ticker)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🧬 BioTerminal Pro")
    st.markdown("---")

    ticker_input = st.text_input(
        "Ticker",
        value="MRNA",
        placeholder="e.g. MRNA, VRTX, 2269.HK",
        help="US tickers (MRNA) or HK tickers (2269.HK / 0700)",
    ).strip().upper()

    if not ticker_input:
        ticker_input = "MRNA"

    period_opts = {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo",
                   "1 Year": "1y", "2 Years": "2y", "5 Years": "5y"}
    period_label = st.selectbox("Period", list(period_opts.keys()), index=3)
    period = period_opts[period_label]

    st.markdown("---")
    adapter = get_exchange_adapter(ticker_input)
    region  = adapter.get_region()
    badge_cls = {"US": "badge-us", "HK": "badge-hk"}.get(region, "badge-neutral")
    st.markdown(
        f"**Region:** <span class='{badge_cls}'>{region}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("Data: yfinance · ClinicalTrials.gov")
    st.caption("For informational purposes only. Not financial advice.")


# ── Load core data ─────────────────────────────────────────────────────────────

with st.spinner(f"Loading data for **{ticker_input}**…"):
    prices_df  = load_prices(ticker_input, period)
    info       = load_info(ticker_input)
    funds      = load_fundamentals(ticker_input)
    news_df    = load_news(ticker_input)
    trials_raw = load_pipeline(ticker_input)

company_name = info.get("name") or ticker_input
currency     = info.get("currency", "USD")

# Price delta
price_delta_pct = None
current_price   = None
if not prices_df.empty:
    current_price   = float(prices_df["Close"].iloc[-1])
    first_price     = float(prices_df["Close"].iloc[0])
    price_delta_pct = (current_price / first_price - 1)

# ── Header ─────────────────────────────────────────────────────────────────────
col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
with col_h1:
    badge_cls = {"US": "badge-us", "HK": "badge-hk"}.get(region, "badge-neutral")
    st.markdown(
        f"## {company_name} &nbsp;<span class='{badge_cls}'>{region}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"{ticker_input} · {info.get('exchange', '')} · {currency}")
with col_h2:
    if current_price is not None:
        st.metric(
            "Price",
            f"{current_price:,.2f} {currency}",
            delta=f"{price_delta_pct*100:+.2f}% ({period_label})" if price_delta_pct else None,
        )
with col_h3:
    mktcap = funds.get("market_cap")
    st.metric("Market Cap", fmt_large(mktcap, currency) if mktcap else "N/A")

st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Overview",
    "📈 Technical",
    "🔬 Pipeline",
    "🤖 Prediction",
    "🏆 Peers",
    "📰 News",
    "⭐ Watchlist",
    "🎯 Alpha Radar",
    "💰 Earnings",
])

(tab_overview, tab_tech, tab_pipeline, tab_pred,
 tab_peers, tab_news, tab_watchlist, tab_alpha, tab_earnings) = tabs


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    # Key metrics row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">P/E Ratio</div>
          <div class="metric-value">{fmt_ratio(funds.get('pe_ratio'))}</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">P/S Ratio</div>
          <div class="metric-value">{fmt_ratio(funds.get('ps_ratio'))}</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">EV / Revenue</div>
          <div class="metric-value">{fmt_ratio(funds.get('ev_revenue'))}</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        beta = funds.get("beta")
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">Beta</div>
          <div class="metric-value">{fmt_num(beta) if beta else 'N/A'}</div>
        </div>""", unsafe_allow_html=True)
    with m5:
        wk52h = funds.get("52wk_high")
        wk52l = funds.get("52wk_low")
        rng   = f"{wk52l:.2f} – {wk52h:.2f}" if wk52h and wk52l else "N/A"
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">52-Week Range</div>
          <div class="metric-value" style="font-size:15px">{rng}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # Price chart
    col_chart, col_desc = st.columns([2, 1])
    with col_chart:
        if not prices_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=prices_df.index, y=prices_df["Close"],
                name="Close", line=dict(color="#60a5fa", width=2),
                fill="tozeroy", fillcolor="rgba(96,165,250,0.07)",
            ))
            fig.update_layout(
                title=f"{ticker_input} Price ({period_label})",
                height=320, showlegend=False,
                margin=dict(l=0, r=0, t=40, b=0),
                **PLOTLY_THEME,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No price data available.")

    with col_desc:
        st.markdown("**Company Overview**")
        desc = info.get("description")
        if desc:
            st.markdown(f'<div style="font-size:13px;color:#94a3b8;line-height:1.6">{desc[:600]}{"…" if len(desc)>600 else ""}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#64748b">No description available.</div>', unsafe_allow_html=True)

        st.markdown("")
        more1, more2 = st.columns(2)
        with more1:
            st.metric("Revenue TTM", fmt_large(funds.get("revenue_ttm"), currency))
            st.metric("Net Income TTM", fmt_large(funds.get("net_income_ttm"), currency))
        with more2:
            st.metric("Cash", fmt_large(funds.get("cash"), currency))
            st.metric("Total Debt", fmt_large(funds.get("total_debt"), currency))

    # Pipeline snapshot
    if not trials_raw.empty:
        enriched = enrich_trials(trials_raw)
        summary  = pipeline_summary(trials_raw)
        st.markdown("---")
        st.markdown("### Pipeline Snapshot")
        ps1, ps2, ps3, ps4 = st.columns(4)
        ps1.metric("Total Trials",     summary["total"])
        ps2.metric("Active Trials",    summary["active"])
        ps3.metric("Phase 3+ Assets",  summary["phase3_plus"])
        ps4.metric("Catalysts (12m)",  summary["catalysts_12m"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TECHNICAL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_tech:
    if prices_df.empty:
        st.warning("No price data available for technical analysis.")
    else:
        sig_df = compute_signals(prices_df.copy())

        # Controls
        tc1, tc2, tc3 = st.columns([2, 1, 1])
        with tc2:
            show_ma  = st.multiselect("Moving Averages", ["SMA20", "SMA50", "SMA200"],
                                       default=["SMA20", "SMA50"])
        with tc3:
            chart_type = st.selectbox("Chart type", ["Line", "Candlestick"])

        # Main price chart with MAs
        fig = make_subplots(
            rows=3, cols=1,
            row_heights=[0.55, 0.20, 0.25],
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=["Price + Volume", "RSI (14)", "MACD"],
        )

        closes = sig_df["Close"].astype(float)
        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=sig_df.index, open=sig_df["Open"], high=sig_df["High"],
                low=sig_df["Low"], close=sig_df["Close"],
                increasing_line_color="#22c55e", decreasing_line_color="#ef4444",
                name="OHLC",
            ), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=sig_df.index, y=closes, name="Close",
                line=dict(color="#60a5fa", width=1.5),
            ), row=1, col=1)

        # Bollinger Bands
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["bb_upper"],
            name="BB Upper", line=dict(color="#475569", width=1, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["bb_lower"],
            name="BB Lower", line=dict(color="#475569", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(71,85,105,0.07)"), row=1, col=1)

        ma_colours = {"SMA20": "#f59e0b", "SMA50": "#a78bfa", "SMA200": "#f472b6"}
        for ma in show_ma:
            period_n = int(ma.replace("SMA", ""))
            ma_vals  = closes.rolling(period_n).mean()
            fig.add_trace(go.Scatter(x=sig_df.index, y=ma_vals, name=ma,
                line=dict(color=ma_colours[ma], width=1.5)), row=1, col=1)

        # Volume
        vol_colours = ["#22c55e" if c >= o else "#ef4444"
                       for c, o in zip(sig_df["Close"], sig_df["Open"])]
        fig.add_trace(go.Bar(x=sig_df.index, y=sig_df["Volume"],
            name="Volume", marker_color=vol_colours, opacity=0.6), row=1, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["rsi"],
            name="RSI", line=dict(color="#a78bfa", width=1.5)), row=2, col=1)
        for lvl, col in [(70, "rgba(239,68,68,0.3)"), (30, "rgba(34,197,94,0.3)")]:
            fig.add_hline(y=lvl, line_dash="dash", line_color=col, row=2, col=1)

        # MACD
        hist_colours = ["#22c55e" if v >= 0 else "#ef4444"
                        for v in sig_df["macd_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=sig_df.index, y=sig_df["macd_hist"],
            name="MACD Hist", marker_color=hist_colours, opacity=0.8), row=3, col=1)
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["macd_line"],
            name="MACD Line", line=dict(color="#60a5fa", width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["macd_signal"],
            name="Signal", line=dict(color="#f59e0b", width=1.5, dash="dot")), row=3, col=1)

        fig.update_layout(
            height=650, showlegend=True,
            legend=dict(orientation="h", y=1.02, x=0),
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=50, b=0),
            **PLOTLY_THEME,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Technical snapshot table
        st.markdown("**Technical Snapshot**")
        rsi_val = sig_df["rsi"].iloc[-1]
        macd_h  = sig_df["macd_hist"].iloc[-1]
        sma20   = closes.rolling(20).mean().iloc[-1]
        sma50   = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else np.nan
        px      = closes.iloc[-1]

        snap = {
            "Current Price":  f"{px:.2f}",
            "RSI (14)":       f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "N/A",
            "MACD Hist":      f"{macd_h:.4f}" if not pd.isna(macd_h) else "N/A",
            "vs SMA-20":      f"{(px/sma20-1)*100:+.2f}%" if not pd.isna(sma20) else "N/A",
            "vs SMA-50":      f"{(px/sma50-1)*100:+.2f}%" if not pd.isna(sma50) else "N/A",
        }
        st.dataframe(
            pd.DataFrame(list(snap.items()), columns=["Indicator", "Value"]),
            use_container_width=True, hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PIPELINE & CATALYSTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_pipeline:
    st.markdown("### Clinical Trial Pipeline")

    if trials_raw.empty:
        st.info("No clinical trial data found. This may be a non-biotech company "
                "or the ticker could not be matched to a ClinicalTrials.gov sponsor.")
    else:
        enriched = enrich_trials(trials_raw)
        summary  = pipeline_summary(trials_raw)

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Studies",     summary["total"])
        c2.metric("Active",            summary["active"])
        c3.metric("Phase 3+ Active",   summary["phase3_plus"])
        c4.metric("Catalysts (12m)",   summary["catalysts_12m"])

        col_pie, col_table = st.columns([1, 2])

        with col_pie:
            breakdown = phase_breakdown(enriched)
            if not breakdown.empty:
                fig_pie = px.pie(
                    breakdown, names="phase", values="count",
                    title="Active Trials by Phase",
                    color_discrete_sequence=px.colors.sequential.Blues_r,
                    hole=0.4,
                )
                fig_pie.update_layout(height=320, **PLOTLY_THEME,
                                      margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_table:
            # rNPV
            assumptions = AssetAssumptions()
            total_rnpv, rnpv_detail = pipeline_rnpv(enriched, assumptions)
            st.metric("Estimated Pipeline rNPV",
                      fmt_large(total_rnpv) if total_rnpv else "N/A",
                      help="Simplified rNPV model. Assumes $500M peak sales per asset. Not investment advice.")

        # Trial table
        st.markdown("**All Trials**")
        display_cols = [c for c in [
            "nct_id", "title", "phase_clean", "status_clean",
            "condition", "primary_completion_date", "prob_approval",
        ] if c in enriched.columns]

        filtered = enriched[display_cols].rename(columns={
            "phase_clean": "Phase", "status_clean": "Status",
            "primary_completion_date": "Primary Completion",
            "prob_approval": "P(Approval)",
        })

        # Phase filter
        phases = ["All"] + list(enriched["phase_clean"].unique())
        sel_phase = st.selectbox("Filter by phase", phases)
        if sel_phase != "All":
            mask = enriched["phase_clean"] == sel_phase
            filtered = filtered[mask.values]

        filtered["P(Approval)"] = filtered["P(Approval)"].map(lambda v: f"{v*100:.1f}%")
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        # Upcoming catalysts
        cats = upcoming_catalysts(enriched, within_days=365)
        if not cats.empty:
            st.markdown("**Upcoming Catalysts (next 12 months)**")
            cat_display = cats[["title", "phase_clean", "condition",
                                 "primary_completion_date", "days_to_primary"]].rename(
                columns={"phase_clean": "Phase",
                         "primary_completion_date": "Completion Date",
                         "days_to_primary": "Days Away"}
            ).head(10)
            st.dataframe(cat_display, use_container_width=True, hide_index=True)

        # Scenario analysis
        if not rnpv_detail.empty:
            with st.expander("rNPV Detail by Asset"):
                rnpv_show = rnpv_detail.copy()
                for col in ["peak_sales", "rnpv", "dev_cost_pv", "net_rnpv"]:
                    if col in rnpv_show.columns:
                        rnpv_show[col] = rnpv_show[col].map(lambda v: fmt_large(v))
                rnpv_show["prob_approval"] = rnpv_show["prob_approval"].map(lambda v: f"{v*100:.1f}%")
                st.dataframe(rnpv_show, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — PREDICTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_pred:
    st.markdown("### ML Prediction Engine")
    st.caption("RandomForest trained on rolling technical + fundamental features. "
               "Predicts 20-day forward outperformance (binary). For informational use only.")

    if prices_df.empty or len(prices_df) < 120:
        st.warning("Insufficient price history for the ML model (need ≥ 120 trading days).")
    else:
        if st.button("Run Prediction", type="primary"):
            with st.spinner("Training model on historical data…"):
                from model import predict as ml_predict
                result = ml_predict(ticker_input, prices_df, funds)

            # Signal display
            sig_colour = {"BULLISH": "signal-bullish",
                          "BEARISH": "signal-bearish",
                          "NEUTRAL": "signal-neutral"}[result.signal]

            p1, p2, p3, p4 = st.columns(4)
            p1.markdown(f"**Signal:** <span class='{sig_colour}'>{result.signal}</span>",
                        unsafe_allow_html=True)
            p2.metric("Confidence", f"{result.confidence*100:.1f}%")
            p3.metric("Bull Probability", f"{result.bull_prob*100:.1f}%")
            p4.metric("Bear Probability", f"{result.bear_prob*100:.1f}%")
            st.metric("Trained on", f"{result.trained_on} samples")

            if not result.feature_df.empty:
                st.markdown("**Feature Importance (top 15)**")
                top_feats = result.feature_df.head(15)
                fig_feat = px.bar(
                    top_feats, x="importance", y="feature",
                    orientation="h",
                    color="importance",
                    color_continuous_scale="Blues",
                    title="Feature Importance",
                )
                fig_feat.update_layout(
                    height=400, showlegend=False,
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=0, r=0, t=40, b=0),
                    **PLOTLY_THEME,
                )
                st.plotly_chart(fig_feat, use_container_width=True)

                # Backtest
                with st.expander("Run Strategy Backtest"):
                    bt_result = run_backtest(prices_df)
                    if bt_result.metrics:
                        m = bt_result.metrics
                        bm1, bm2, bm3, bm4 = st.columns(4)
                        bm1.metric("Total Return",   f"{m['total_return_pct']:+.1f}%")
                        bm2.metric("Sharpe Ratio",   f"{m['sharpe_ratio']:.2f}")
                        bm3.metric("Max Drawdown",   f"{m['max_drawdown_pct']:.1f}%")
                        bm4.metric("Alpha vs B&H",   f"{m['alpha_pct']:+.1f}%")

                        if not bt_result.equity_curve.empty:
                            fig_eq = go.Figure()
                            fig_eq.add_trace(go.Scatter(
                                x=bt_result.equity_curve.index,
                                y=bt_result.equity_curve.values,
                                name="Strategy", line=dict(color="#60a5fa"),
                            ))
                            # B&H overlay
                            bh = (prices_df["Close"] / prices_df["Close"].iloc[0]) * 100_000
                            fig_eq.add_trace(go.Scatter(
                                x=bh.index, y=bh.values,
                                name="Buy & Hold", line=dict(color="#f59e0b", dash="dot"),
                            ))
                            fig_eq.update_layout(
                                title="Equity Curve", height=300,
                                margin=dict(l=0, r=0, t=40, b=0),
                                **PLOTLY_THEME,
                            )
                            st.plotly_chart(fig_eq, use_container_width=True)
        else:
            st.info("Click **Run Prediction** to train the model on available price history.")

        # Devil's Advocate
        st.markdown("---")
        st.markdown("### Devil's Advocate — Bear Case Analysis")
        if st.button("Analyse Risk Factors"):
            from devils_advocate import analyse, risk_summary
            with st.spinner("Analysing risk factors…"):
                risks = analyse(ticker_input, prices_df, funds, trials_raw, info)
            summary_d = risk_summary(risks)

            sev_col = {"CRITICAL": "#ef4444", "HIGH": "#f97316",
                       "MEDIUM": "#f59e0b", "LOW": "#22c55e"}
            colour = sev_col.get(summary_d["overall"], "#94a3b8")
            st.markdown(
                f"**Overall Risk Level:** "
                f'<span style="color:{colour};font-weight:700">{summary_d["overall"]}</span>'
                f" &nbsp;({summary_d['count']} risk factors identified)",
                unsafe_allow_html=True,
            )

            for rf in risks:
                sev_col_cls = f"sev-{rf.severity}"
                with st.expander(f"[{'★'*rf.severity}] {rf.category}: {rf.title}"):
                    st.markdown(rf.detail)
                    st.caption(f"Evidence: {rf.evidence}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PEER COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
with tab_peers:
    st.markdown("### Peer Comparison")

    auto_peers = df_mod.get_peers(ticker_input)
    peer_input = st.text_input(
        "Peer tickers (comma-separated)",
        value=", ".join(auto_peers),
        help="Edit to customise peer group",
    )
    peer_list = [p.strip().upper() for p in peer_input.split(",") if p.strip()]

    if peer_list:
        all_tickers = [ticker_input] + [p for p in peer_list if p != ticker_input]

        with st.spinner("Fetching peer data…"):
            peer_rows = []
            for pt in all_tickers:
                pf = load_fundamentals(pt)
                pp = load_prices(pt, "1y")
                ret_1y = float(pp["Close"].iloc[-1] / pp["Close"].iloc[0] - 1) * 100 if not pp.empty and len(pp) > 1 else np.nan
                peer_rows.append({
                    "Ticker":        pt,
                    "Market Cap":    fmt_large(pf.get("market_cap"), "USD"),
                    "P/E":           fmt_ratio(pf.get("pe_ratio")),
                    "P/S":           fmt_ratio(pf.get("ps_ratio")),
                    "EV/Rev":        fmt_ratio(pf.get("ev_revenue")),
                    "Beta":          fmt_num(pf.get("beta")),
                    "Rev Growth":    fmt_pct(pf.get("revenue_growth")),
                    "Profit Margin": fmt_pct(pf.get("profit_margin")),
                    "1Y Return":     f"{ret_1y:+.1f}%" if not np.isnan(ret_1y) else "N/A",
                })

        peer_df = pd.DataFrame(peer_rows)
        st.dataframe(peer_df, use_container_width=True, hide_index=True)

        # Performance comparison chart
        st.markdown("**12-Month Price Performance (Indexed to 100)**")
        fig_peer = go.Figure()
        colours = ["#60a5fa", "#22c55e", "#f59e0b", "#a78bfa",
                   "#f472b6", "#34d399", "#fb923c", "#818cf8"]
        for i, pt in enumerate(all_tickers):
            pp = load_prices(pt, "1y")
            if not pp.empty:
                indexed = pp["Close"] / pp["Close"].iloc[0] * 100
                fig_peer.add_trace(go.Scatter(
                    x=pp.index, y=indexed, name=pt,
                    line=dict(color=colours[i % len(colours)],
                              width=2.5 if pt == ticker_input else 1.5),
                ))
        fig_peer.update_layout(
            height=380, margin=dict(l=0, r=0, t=20, b=0), **PLOTLY_THEME
        )
        st.plotly_chart(fig_peer, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — NEWS & FILINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_news:
    st.markdown("### News & Filings")

    col_news, col_filings = st.columns([3, 2])

    with col_news:
        st.markdown("**Recent News**")
        if news_df.empty:
            st.info("No news available.")
        else:
            for _, row in news_df.dropna(subset=["title"]).head(15).iterrows():
                date_str = str(row.get("date", ""))[:10] if row.get("date") else ""
                url      = row.get("url", "#")
                title    = row.get("title", "")
                source   = row.get("source", "")
                st.markdown(
                    f'<div style="padding:10px;border-left:2px solid #1e3a5f;margin-bottom:8px">'
                    f'<div style="font-size:11px;color:#475569">{date_str} · {source}</div>'
                    f'<a href="{url}" target="_blank" style="color:#60a5fa;text-decoration:none;font-size:14px">{title}</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with col_filings:
        st.markdown("**Filings**")
        filings_df = df_mod.get_filings(ticker_input, limit=10)
        if filings_df.empty:
            st.info("No filings data available for this region yet.")
        else:
            for _, row in filings_df.head(10).iterrows():
                date_str = str(row.get("date", ""))[:10]
                url      = row.get("url", "#")
                title    = row.get("title", row.get("title", ""))[:80]
                st.markdown(
                    f'<div style="padding:8px;border-left:2px solid #1e2035;margin-bottom:6px">'
                    f'<div style="font-size:11px;color:#475569">{date_str}</div>'
                    f'<a href="{url}" target="_blank" style="color:#94a3b8;font-size:13px">{title}</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_watchlist:
    st.markdown("### Watchlist")

    wl_c1, wl_c2 = st.columns([3, 1])
    with wl_c1:
        new_ticker = st.text_input("Add ticker", placeholder="e.g. AAPL, 0700.HK")
    with wl_c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add", type="primary") and new_ticker:
            t = new_ticker.strip().upper()
            if t and t not in st.session_state.watchlist:
                st.session_state.watchlist.append(t)
                st.rerun()

    if st.session_state.watchlist:
        wl_rows = []
        for wt in st.session_state.watchlist:
            try:
                wp  = load_prices(wt, "1mo")
                wf  = load_fundamentals(wt)
                wpx = float(wp["Close"].iloc[-1]) if not wp.empty else np.nan
                wr  = float(wp["Close"].iloc[-1] / wp["Close"].iloc[0] - 1) * 100 if not wp.empty and len(wp) > 1 else np.nan
                wl_rows.append({
                    "Ticker":   wt,
                    "Price":    f"{wpx:.2f}" if not np.isnan(wpx) else "N/A",
                    "1M Return":f"{wr:+.1f}%" if not np.isnan(wr) else "N/A",
                    "Mkt Cap":  fmt_large(wf.get("market_cap")),
                    "P/S":      fmt_ratio(wf.get("ps_ratio")),
                    "Remove":   wt,
                })
            except Exception:
                wl_rows.append({"Ticker": wt, "Price": "—", "1M Return": "—",
                                 "Mkt Cap": "—", "P/S": "—", "Remove": wt})

        wl_df = pd.DataFrame(wl_rows)
        st.dataframe(wl_df.drop(columns=["Remove"]), use_container_width=True, hide_index=True)

        # Remove
        remove_t = st.selectbox("Remove from watchlist", [""] + st.session_state.watchlist)
        if remove_t and st.button("Remove", type="secondary"):
            st.session_state.watchlist.remove(remove_t)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 — ALPHA RADAR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_alpha:
    st.markdown("### Alpha Radar — Biotech Screener")
    st.caption("Screens the default biotech universe. Scores on momentum, value, pipeline, quality, and technical signals.")

    ar_c1, ar_c2, ar_c3 = st.columns([1, 1, 1])
    with ar_c1:
        screen_region = st.selectbox("Region", ["US", "HK"])
    with ar_c2:
        top_n = st.slider("Top N", 5, 20, 10)
    with ar_c3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_screen_btn = st.button("Run Screen", type="primary")

    if run_screen_btn:
        from alpha_screener import run_screen
        with st.spinner(f"Screening {screen_region} biotech universe…"):
            screen_df = run_screen(region=screen_region, top_n=top_n)

        if screen_df.empty:
            st.warning("Screening returned no results. Try again in a moment.")
        else:
            # Score bar chart
            fig_score = px.bar(
                screen_df, x="ticker", y="total_score",
                color="total_score",
                color_continuous_scale="Blues",
                title=f"Top {len(screen_df)} Biotech Alpha Scores ({screen_region})",
            )
            fig_score.update_layout(height=360, margin=dict(l=0, r=0, t=40, b=0),
                                     **PLOTLY_THEME, coloraxis_showscale=False)
            st.plotly_chart(fig_score, use_container_width=True)

            # Score breakdown radar — top 5
            top5 = screen_df.head(5)
            dims = ["momentum", "value", "pipeline", "quality", "technical"]
            fig_radar = go.Figure()
            radar_colours = ["#60a5fa", "#22c55e", "#f59e0b", "#a78bfa", "#f472b6"]
            for i, (_, row) in enumerate(top5.iterrows()):
                vals = [row[d] for d in dims] + [row[dims[0]]]
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals, theta=dims + [dims[0]],
                    name=row["ticker"],
                    line=dict(color=radar_colours[i]),
                    fill="toself", fillcolor=radar_colours[i].replace("fa", "1a"),
                    opacity=0.6,
                ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(range=[0, 20])),
                height=420, **PLOTLY_THEME,
                title="Score Breakdown — Top 5",
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            # Data table
            display_df = screen_df.copy()
            if "market_cap" in display_df.columns:
                display_df["market_cap"] = display_df["market_cap"].apply(
                    lambda v: fmt_large(v) if v else "N/A"
                )
            if "revenue_growth" in display_df.columns:
                display_df["revenue_growth"] = display_df["revenue_growth"].apply(fmt_pct)
            if "ps_ratio" in display_df.columns:
                display_df["ps_ratio"] = display_df["ps_ratio"].apply(fmt_ratio)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Click **Run Screen** to score the biotech universe.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 9 — EARNINGS INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_earnings:
    st.markdown("### Earnings Intelligence")

    with st.spinner("Loading earnings data…"):
        earn = load_earnings(ticker_input)

    # Summary header
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Next Earnings",    earn.get("next_earnings_date") or "N/A")
    beat = earn.get("beat_rate_8q")
    e2.metric("Beat Rate (8Q)",   f"{beat*100:.0f}%" if beat and not np.isnan(beat) else "N/A")
    surp = earn.get("avg_surprise_pct")
    e3.metric("Avg EPS Surprise", f"{surp:+.1f}%" if surp and not np.isnan(surp) else "N/A")
    cagr = earn.get("revenue_cagr_3y")
    e4.metric("Rev CAGR (3Y)",    f"{cagr*100:.1f}%" if cagr and not np.isnan(cagr) else "N/A")

    # Analyst targets
    st.markdown("---")
    tgt_m = earn.get("target_mean")
    tgt_h = earn.get("target_high")
    tgt_l = earn.get("target_low")
    rec   = earn.get("recommendation", "")
    n_ana = earn.get("n_analysts")

    if tgt_m:
        upside = (tgt_m / current_price - 1) * 100 if current_price else None
        at1, at2, at3, at4 = st.columns(4)
        at1.metric("Consensus Target", f"{tgt_m:.2f}")
        at2.metric("Upside/Downside",  f"{upside:+.1f}%" if upside else "N/A")
        at3.metric("Rating",           rec or "N/A")
        at4.metric("# Analysts",       str(n_ana) if n_ana else "N/A")

    col_eps, col_rev = st.columns(2)

    with col_eps:
        st.markdown("**Quarterly EPS History**")
        eps_df = earn.get("quarterly_eps_df", pd.DataFrame())
        if not eps_df.empty and "Reported EPS" in eps_df.columns:
            fig_eps = go.Figure()
            if "Estimated EPS" in eps_df.columns:
                fig_eps.add_trace(go.Bar(
                    x=eps_df.iloc[:, 0], y=eps_df["Estimated EPS"],
                    name="Estimate", marker_color="#475569", opacity=0.7,
                ))
            colours = ["#22c55e" if b else "#ef4444"
                       for b in eps_df.get("Beat", [False]*len(eps_df))]
            fig_eps.add_trace(go.Bar(
                x=eps_df.iloc[:, 0], y=eps_df["Reported EPS"],
                name="Reported", marker_color=colours,
            ))
            fig_eps.update_layout(
                barmode="overlay", height=280,
                margin=dict(l=0, r=0, t=20, b=0),
                **PLOTLY_THEME,
            )
            st.plotly_chart(fig_eps, use_container_width=True)
        else:
            st.info("Quarterly EPS data not available.")

    with col_rev:
        st.markdown("**Annual Revenue Trend**")
        rev_df = earn.get("annual_revenue_df", pd.DataFrame())
        if not rev_df.empty and "Revenue" in rev_df.columns:
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(
                x=rev_df["Date"].astype(str), y=rev_df["Revenue"],
                marker_color="#60a5fa", name="Revenue",
            ))
            fig_rev.update_layout(
                height=280, margin=dict(l=0, r=0, t=20, b=0),
                yaxis_title="Revenue ($)",
                **PLOTLY_THEME,
            )
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("Annual revenue data not available.")

    if not eps_df.empty:
        with st.expander("EPS Detail Table"):
            st.dataframe(eps_df, use_container_width=True, hide_index=True)
