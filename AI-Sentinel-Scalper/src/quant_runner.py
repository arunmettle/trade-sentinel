from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class QuantMetrics:
    net_profit_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    win_rate: float
    trade_count: int


@dataclass
class QuantReport:
    strategy_id: str
    period: dict
    metrics: QuantMetrics
    verdict: str
    observation: str


def _max_drawdown_from_equity(equity_curve):
    peak = equity_curve.cummax()
    dd = (equity_curve - peak) / peak
    return abs(float(dd.min()))


def _sanitize_returns(returns, max_abs_ret: float = 0.10):
    """Clip extreme minute returns to reduce data-artifact explosions.

    Default 10%/minute cap is conservative for BTC 1m and meant for robustness.
    """
    return returns.clip(lower=-max_abs_ret, upper=max_abs_ret)


def run_vectorized_backtest(
    csv_path: str | Path,
    strategy_id: str = "v1_baseline",
    fee_pct: float = 0.0006,
    slippage_pct: float = 0.0002,
    max_abs_ret: float = 0.10,
) -> QuantReport:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "close" not in df.columns:
        raise ValueError("CSV must include at least a 'close' column")

    close = df["close"].astype(float)
    returns = close.pct_change().fillna(0.0)
    returns = _sanitize_returns(returns, max_abs_ret=max_abs_ret)

    # Baseline signal: momentum proxy (replace with Architect strategy wiring later)
    momentum = returns.rolling(14).mean().fillna(0)
    signal = np.where(momentum > 0, 1.0, 0.0)

    signal_s = pd.Series(signal, index=df.index, dtype="float64")
    prev_signal = signal_s.shift(1).fillna(0.0)
    entries = (signal_s == 1.0) & (prev_signal == 0.0)
    exits = (signal_s == 0.0) & (prev_signal == 1.0)

    per_bar_cost = (entries.astype(float) + exits.astype(float)) * (fee_pct + slippage_pct)
    strat_returns = (signal_s * returns) - per_bar_cost

    equity = (1 + strat_returns).cumprod()
    net_profit_pct = float(equity.iloc[-1] - 1)
    mdd = _max_drawdown_from_equity(equity)

    vol = float(strat_returns.std())
    sharpe = 0.0 if vol == 0 else float((strat_returns.mean() / vol) * np.sqrt(365 * 24 * 60))

    gross_profit = float(strat_returns[strat_returns > 0].sum())
    gross_loss = abs(float(strat_returns[strat_returns < 0].sum()))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Trade-level win rate: pair each entry with next exit, use compounded trade return.
    entry_idx = list(df.index[entries])
    exit_idx = list(df.index[exits])
    if exit_idx and entry_idx and exit_idx[0] < entry_idx[0]:
        exit_idx = exit_idx[1:]

    n = min(len(entry_idx), len(exit_idx))
    wins = 0
    for i in range(n):
        s = entry_idx[i]
        e = exit_idx[i]
        if e <= s:
            continue
        trade_slice = strat_returns.loc[s:e]
        trade_ret = float((1 + trade_slice).prod() - 1)
        if trade_ret > 0:
            wins += 1

    trade_count = n
    win_rate = (wins / trade_count) if trade_count > 0 else 0.0

    verdict = "validated_for_demo" if sharpe > 2.0 and mdd < 0.015 else "hold"

    period = {
        "start": str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else "unknown",
        "end": str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else "unknown",
    }

    report = QuantReport(
        strategy_id=strategy_id,
        period=period,
        metrics=QuantMetrics(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=mdd,
            sharpe_ratio=sharpe,
            profit_factor=pf,
            win_rate=win_rate,
            trade_count=trade_count,
        ),
        verdict=verdict,
        observation=(
            "Vectorized baseline with clipped minute-return outlier handling and trade-level win-rate. "
            "Replace signal with strategy contract input for production."
        ),
    )
    return report


def save_report(report: QuantReport, out_path: str | Path) -> None:
    payload = asdict(report)
    payload["metrics"] = asdict(report.metrics)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(out_path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
