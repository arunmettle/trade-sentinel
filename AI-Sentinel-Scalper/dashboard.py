from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE = Path(__file__).resolve().parent

st.set_page_config(page_title="AI-Sentinel Dashboard", layout="wide")
st.title("🤖 AI-Sentinel: Bybit Scalper")


def read_json(path: Path, default: dict):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_memory(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return "No journal entries yet."


live_cfg = read_json(BASE / "config" / "live_config.json", {})
runtime = read_json(BASE / "logs" / "runtime_state.json", {})
guardian = read_json(BASE / "logs" / "guardian_state.json", {})
strategy = read_json(BASE / "config" / "live_strategy.json", {})
sentiment = read_json(BASE / "config" / "sentiment_gate.json", {})

with st.sidebar:
    st.header("System Health")
    st.metric("Trade Mode", runtime.get("trade_mode", {}).get("mode", "UNKNOWN"))
    st.metric("Sentiment", f"{sentiment.get('score', 'n/a')}/100", sentiment.get("status", "n/a"))
    st.metric("Guardian Dry Run", str(live_cfg.get("runtime", {}).get("dry_run", True)))
    st.metric("Regime", strategy.get("regime", "n/a"))

    if not sentiment.get("allow_trading", True):
        st.error("Sentiment gate blocking new trades")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current Equity", guardian.get("current_equity", "n/a"))
with col2:
    st.metric("Drawdown", f"{guardian.get('drawdown', 0):.2%}" if guardian.get("drawdown") is not None else "n/a")
with col3:
    st.metric("Lock Threshold", f"{guardian.get('lock_threshold', 0):.2%}" if guardian.get("lock_threshold") is not None else "n/a")

# Placeholder equity curve until trade history wiring lands
curve = pd.DataFrame(
    {
        "time": pd.date_range(end=datetime.now(), periods=10, freq="h"),
        "equity": [1000, 1005, 1002, 1010, 1008, 1015, 1013, 1018, 1022, 1020],
    }
)
fig = go.Figure()
fig.add_trace(go.Scatter(x=curve["time"], y=curve["equity"], mode="lines+markers", name="Equity"))
fig.update_layout(title="Equity Curve (placeholder)", template="plotly_dark", height=380)
st.plotly_chart(fig, use_container_width=True)

tab1, tab2, tab3 = st.tabs(["Open State", "Reasoning/Runtime", "Journal Memory"])
with tab1:
    st.subheader("Strategy")
    st.json(strategy)
    st.subheader("Sentiment Gate")
    st.json(sentiment)
with tab2:
    st.subheader("Runtime State")
    st.json(runtime)
    st.subheader("Guardian State")
    st.json(guardian)
with tab3:
    st.subheader("long_term_memory.md")
    st.markdown(read_memory(BASE / "memory" / "long_term_memory.md"))

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
