from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class RegimeParams:
    hurdle_multiplier: float
    min_trade_usd: float
    label: str


def classify_regime(adr_ratio: float) -> RegimeParams:
    if adr_ratio < 0.85:
        return RegimeParams(3.5, 500, "CRUISE")
    if adr_ratio > 1.25:
        return RegimeParams(1.5, 100, "STORM")
    return RegimeParams(2.0, 300, "HUNT")


def _sim(df: pd.DataFrame, dynamic: bool = True) -> dict:
    # BTC-only regime-aware dry backtest scaffold on historical 1m candles.
    fee = 0.0006
    slippage = 0.0005  # 5 bps institutional friction
    cash = 10000.0
    qty = 0.0
    equity_curve = []

    # simple sentiment proxy from normalized momentum
    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0)
    score = (50 + (ret.rolling(30).mean() / (ret.rolling(30).std().replace(0, np.nan))).fillna(0) * 10).clip(0, 100)

    # ADR ratio on rolling ranges
    rng = (df["high"].astype(float) - df["low"].astype(float)).abs()
    adr20 = rng.rolling(20).mean().bfill()
    adr3 = rng.rolling(3).mean().bfill()
    ratio = (adr3 / adr20.replace(0, np.nan)).fillna(1.0)

    regime_stats = {"CRUISE": {"pnl": 0.0, "n": 0}, "HUNT": {"pnl": 0.0, "n": 0}, "STORM": {"pnl": 0.0, "n": 0}}
    prev_eq = cash
    trades = 0

    fixed_capital = 10000.0

    for i in range(len(df)):
        # latency model: execute using next bar price (proxy for 500ms delay on 1m bars)
        exec_i = min(i + 1, len(df) - 1)
        px = float(close.iloc[exec_i])
        sc = float(score.iloc[i])
        rr = float(ratio.iloc[i])
        params = classify_regime(rr) if dynamic else RegimeParams(2.0, 300, "HUNT")

        expected_move = max(0.0, (sc - 50) / 50) * 0.01
        hurdle = (fee + slippage) * params.hurdle_multiplier

        # target delta proxy
        target_delta = max(0.0, min(0.5, (sc - 50) / 50 * 0.5))
        # disable compounding: fixed position budget regardless equity growth
        target_notional = fixed_capital * target_delta
        target_qty = target_notional / px if px > 0 else 0.0
        diff = target_qty - qty
        notional = abs(diff) * px

        if notional >= params.min_trade_usd and expected_move > hurdle:
            fees = notional * (fee + slippage)
            alpha = notional * expected_move * 0.22
            cash += -diff * px - fees + alpha
            qty = target_qty
            trades += 1

        eq = cash + qty * px
        pnl_step = eq - prev_eq
        regime_stats[params.label]["pnl"] += pnl_step
        regime_stats[params.label]["n"] += 1
        prev_eq = eq
        equity_curve.append(eq)

    arr = np.array(equity_curve)
    rets = np.diff(arr) / arr[:-1]
    mu = float(rets.mean()) if len(rets) else 0.0
    sd = float(rets.std()) if len(rets) else 0.0
    sharpe = (mu / sd * math.sqrt(365 * 24 * 60)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(arr)
    mdd = float(abs(((arr - peak) / peak).min())) if len(arr) else 0.0

    for k, v in regime_stats.items():
        n = max(v["n"], 1)
        v["avg_pnl_per_bar"] = v["pnl"] / n

    return {
        "final_equity": float(arr[-1]),
        "profit_pct": float((arr[-1] - 10000.0) / 10000.0),
        "sharpe": sharpe,
        "max_drawdown_pct": mdd,
        "trade_count": trades,
        "regime_stats": regime_stats,
    }


def run_regime_backtest(csv_path: str | Path) -> dict:
    df = pd.read_csv(csv_path)
    required = {"high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError("CSV must include high/low/close")

    dynamic = _sim(df, dynamic=True)
    static = _sim(df, dynamic=False)
    return {"dynamic": dynamic, "static": static}


def save_results(results: dict, out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    d = results["dynamic"]
    s = results["static"]
    lines = [
        "# Regime-Aware Backtest",
        "",
        "## Summary",
        f"- Dynamic profit: {d['profit_pct']:.4%}",
        f"- Dynamic sharpe: {d['sharpe']:.3f}",
        f"- Dynamic mdd: {d['max_drawdown_pct']:.4%}",
        f"- Dynamic trades: {d['trade_count']}",
        f"- Static profit: {s['profit_pct']:.4%}",
        f"- Static sharpe: {s['sharpe']:.3f}",
        f"- Static mdd: {s['max_drawdown_pct']:.4%}",
        f"- Static trades: {s['trade_count']}",
        "",
        "## Regime Performance (Dynamic)",
    ]
    for r, stats in d["regime_stats"].items():
        lines.append(f"- {r}: pnl={stats['pnl']:.4f}, bars={stats['n']}, avg_pnl_per_bar={stats['avg_pnl_per_bar']:.6f}")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
