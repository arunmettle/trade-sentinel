from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.exchange_client import ExchangeClient, force_sync_state

BASE = Path(__file__).resolve().parent

st.set_page_config(page_title="AI-Sentinel Pro Dashboard", layout="wide")
st.title("🛰️ AI-Sentinel — Professional Tactical Console")


# ---------- Helpers ----------
def read_json(path: Path, default: dict):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def read_jsonl(path: Path, limit: int = 200) -> pd.DataFrame:
    rows = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    except Exception:
        return pd.DataFrame()
    if limit and len(rows) > limit:
        rows = rows[-limit:]
    return pd.DataFrame(rows)


def tail_lines(path: Path, n: int = 10) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-n:]) if lines else "(empty)"
    except Exception:
        return "(missing)"


def read_memory(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return "No journal entries yet."


def create_regime_gauge(current_ratio: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=current_ratio,
            title={"text": "Market Regime (ADR Ratio)"},
            delta={"reference": 1.0},
            gauge={
                "axis": {"range": [0, 2]},
                "bar": {"color": "white"},
                "steps": [
                    {"range": [0, 0.85], "color": "royalblue"},  # CRUISE
                    {"range": [0.85, 1.25], "color": "seagreen"},  # HUNT
                    {"range": [1.25, 2], "color": "crimson"},  # STORM
                ],
                "threshold": {
                    "line": {"color": "yellow", "width": 4},
                    "thickness": 0.75,
                    "value": current_ratio,
                },
            },
        )
    )
    fig.update_layout(height=290, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def regime_color(regime: str) -> str:
    return {"CRUISE": "🔵", "HUNT": "🟢", "STORM": "🔴"}.get(regime, "⚪")


# ---------- Load State ----------
live_cfg = read_json(BASE / "config" / "live_config.json", {})
runtime = read_json(BASE / "logs" / "runtime_state.json", {})
guardian = read_json(BASE / "logs" / "guardian_state.json", {})
strategy = read_json(BASE / "config" / "live_strategy.json", {})
sentiment = read_json(BASE / "config" / "sentiment_gate.json", {})
regime_adv = runtime.get("regime_advisory") or {}

sim_trades = read_csv(BASE / "logs" / "sim_trades.csv")
rebalances = read_csv(BASE / "logs" / "rebalance_events.csv")

# ---------- Inconsistency Alarm (zero-trust UI) ----------
btc_target = float(((runtime.get("hybrid") or {}).get("BTC/USDT:USDT") or {}).get("target_delta") or 0.0)
btc_actual = float(((guardian.get("drift_checks") or {}).get("BTC/USDT:USDT") or {}).get("actual_delta") or 0.0)
state_gap = abs(btc_actual - btc_target)

if state_gap > 0.05:
    first_ts = st.session_state.get("mismatch_first_ts")
    if first_ts is None:
        st.session_state["mismatch_first_ts"] = datetime.now().timestamp()
        first_ts = st.session_state["mismatch_first_ts"]
    if datetime.now().timestamp() - float(first_ts) > 30:
        st.error("⚠️ CRITICAL: EXCHANGE/BOT STATE MISMATCH")
        if state_gap > 10:
            st.error("⚠️ Delta calculation unstable (near-zero spot leg with open perp). Use Close-All + Re-Sync.")
else:
    st.session_state.pop("mismatch_first_ts", None)


# ---------- Sidebar Controls ----------
with st.sidebar:
    st.header("System Controls")
    st.caption("Advisory controls (non-executing in dashboard)")

    override = st.selectbox("Regime Override", ["AUTO", "CRUISE", "HUNT", "STORM"], index=0)
    if st.button("Apply Override (advisory)"):
        payload = {
            "override": override,
            "updated_at": datetime.now().isoformat(),
            "source": "dashboard",
        }
        (BASE / "logs" / "regime_override.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        st.success(f"Override set to {override} (advisory file updated)")

    safety_lock = st.checkbox("Safety Lock: enable destructive actions")
    st.caption("Exchange actions use BYBIT_API_KEY/BYBIT_API_SECRET from environment.")

    if st.button("Emergency Close (flag)"):
        payload = {
            "emergency_close": True,
            "updated_at": datetime.now().isoformat(),
            "source": "dashboard",
        }
        (BASE / "logs" / "emergency_close.flag.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        st.error("Emergency close flag written (requires executor/guardian handler)")

    if safety_lock and st.button("🚨 EMERGENCY: CLOSE ALL POSITIONS"):
        try:
            client = ExchangeClient(
                testnet=bool(live_cfg.get("exchange", {}).get("testnet", True)),
            )
            result = client.close_all_positions(symbol="BTCUSDT")
            sync = force_sync_state(
                BASE,
                symbol="BTCUSDT",
            )
            st.error("Close-All executed.")
            st.json({"close_all_result": result, "sync": sync})
        except Exception as e:
            st.error(f"Close-All failed: {e}")

    if st.button("Re-Sync from Exchange (request)"):
        try:
            sync = force_sync_state(
                BASE,
                symbol="BTCUSDT",
            )
            st.warning("Re-sync completed from exchange truth.")
            st.json(sync)
        except Exception as e:
            st.error(f"Re-sync failed: {e}")

    st.divider()
    st.write("Current Regime Advisory:")
    st.json(regime_adv)


# ---------- Top Ribbon ----------
active_regime = str(regime_adv.get("active_regime", "HUNT"))
adr_ratio = float(regime_adv.get("adr_ratio", 1.0) or 1.0)

hybrid = runtime.get("hybrid") or {}
deltas = []
if isinstance(hybrid, dict):
    for _, v in hybrid.items():
        if isinstance(v, dict) and isinstance(v.get("target_delta"), (int, float)):
            deltas.append(float(v["target_delta"]))

total_delta = sum(deltas)

drift_checks = guardian.get("drift_checks") or {}
drift_vals = [
    v.get("drift")
    for v in drift_checks.values()
    if isinstance(v, dict) and isinstance(v.get("drift"), (int, float))
]
max_drift = max(drift_vals) if drift_vals else 0.0

fees_24h = float(sim_trades["fee"].sum()) if not sim_trades.empty and "fee" in sim_trades.columns else 0.0

k1, k2, k3, k4 = st.columns(4)
# System Integrity LED
integrity_gap = state_gap
if integrity_gap <= 0.01:
    integrity = "🟢 GREEN"
elif integrity_gap <= 0.05:
    integrity = "🟡 YELLOW"
else:
    integrity = "🔴 RED"

k1.metric("Regime Status", f"{regime_color(active_regime)} {active_regime}")
k2.metric("Total Delta", f"{total_delta:.3f}")
k3.metric("Drift Meter (max)", f"{max_drift:.2%}" if max_drift <= 10 else "N/A")
k4.metric("System Integrity", integrity)


# ---------- Main Deck ----------
left, right = st.columns([1.2, 1.0])

with left:
    st.plotly_chart(create_regime_gauge(adr_ratio), use_container_width=True)

    st.subheader("ADR Regime Sensor")
    adr_df = read_jsonl(BASE / "logs" / "adr_history.jsonl", limit=240)
    if not adr_df.empty and {"ts", "adr_ratio"}.issubset(adr_df.columns):
        adr_df = adr_df.reset_index(drop=True)
        adr_df["idx"] = adr_df.index
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=adr_df["idx"], y=adr_df["adr_ratio"], mode="lines", name="ADR Ratio"))
        fig.add_hline(y=0.85, line_dash="dot", line_color="royalblue")
        fig.add_hline(y=1.25, line_dash="dot", line_color="crimson")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ADR history available yet.")

with right:
    st.subheader("Alpha vs Friction")

    gross_notional = float(sim_trades["notional"].sum()) if not sim_trades.empty and "notional" in sim_trades.columns else 0.0
    total_fees = fees_24h
    # Slippage proxy until explicit executed-vs-requested logging exists
    slippage_proxy = gross_notional * 0.0005 if gross_notional > 0 else 0.0
    net_alpha = gross_notional - (total_fees + slippage_proxy)

    a1, a2, a3 = st.columns(3)
    a1.metric("Gross Notional (sim)", f"${gross_notional:,.2f}")
    a2.metric("Slippage Proxy", f"${slippage_proxy:,.2f}")
    a3.metric("Net Alpha Proxy", f"${net_alpha:,.2f}")

    st.subheader("Sentiment Heatmap")
    scores = sentiment.get("scores") if isinstance(sentiment.get("scores"), dict) else {}
    if scores:
        s_df = pd.DataFrame([scores])
        st.dataframe(s_df, use_container_width=True)
    else:
        st.info("No per-symbol sentiment scores yet.")


# ---------- Friction Summary ----------
st.subheader("Friction Summary Table")
if not sim_trades.empty and {"symbol", "fee", "notional"}.issubset(sim_trades.columns):
    grp = (
        sim_trades.groupby("symbol", as_index=False)
        .agg(fees_paid=("fee", "sum"), gross_notional=("notional", "sum"), trades=("symbol", "count"))
    )
    grp["avg_slippage_proxy_pct"] = 0.05
    grp["net_vs_gross_pct"] = np.where(
        grp["gross_notional"] > 0,
        ((grp["gross_notional"] - grp["fees_paid"]) / grp["gross_notional"]) * 100,
        0,
    )
    st.dataframe(grp, use_container_width=True)
else:
    st.info("No simulated trades yet for friction summary.")


# ---------- Logs / Runtime ----------
l1, l2 = st.columns(2)
with l1:
    st.subheader("Guardian Live Log (tail)")
    st.code(tail_lines(BASE / "logs" / "guardian.log", 10), language="text")

with l2:
    st.subheader("Runtime State")
    st.json(runtime)


# ---------- Details Tabs ----------
tab1, tab2, tab3 = st.tabs(["Open State", "Rebalance Events", "Journal Memory"])
with tab1:
    st.subheader("Strategy")
    st.json(strategy)
    st.subheader("Sentiment Gate")
    st.json(sentiment)
with tab2:
    st.subheader("Recent Rebalances")
    if rebalances.empty:
        st.info("No rebalance events yet.")
    else:
        st.dataframe(rebalances.tail(20), use_container_width=True)
with tab3:
    st.subheader("long_term_memory.md")
    st.markdown(read_memory(BASE / "memory" / "long_term_memory.md"))

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.info("Tip: enable Streamlit auto-refresh plugin or browser auto-refresh every 5s for near-live monitoring.")
