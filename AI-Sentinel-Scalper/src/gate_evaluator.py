from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GateThresholds:
    min_sharpe: float = 2.0
    max_mdd: float = 0.015
    demo_tolerance_pct: float = 0.15


def evaluate_backtest(sharpe_ratio: float, max_drawdown_pct: float, t: GateThresholds | None = None) -> str:
    t = t or GateThresholds()
    if sharpe_ratio >= t.min_sharpe and max_drawdown_pct <= t.max_mdd:
        return "pass"
    return "fail"


def evaluate_promotion(backtest_pnl: float, demo_pnl: float, t: GateThresholds | None = None) -> str:
    t = t or GateThresholds()
    # Avoid division instability
    base = abs(backtest_pnl) if abs(backtest_pnl) > 1e-9 else 1e-9
    drift = abs(demo_pnl - backtest_pnl) / base
    return "promote" if drift <= t.demo_tolerance_pct else "hold"
