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


@dataclass
class QuantReport:
    strategy_id: str
    period: dict
    metrics: QuantMetrics
    verdict: str
    observation: str


def _max_drawdown_from_equity(equity_curve) -> float:
    peak = equity_curve.cummax()
    dd = (equity_curve - peak) / peak
    return abs(float(dd.min()))


def run_vectorized_backtest(
    csv_path: str | Path,
    strategy_id: str = "v1_baseline",
    fee_pct: float = 0.0006,
    slippage_pct: float = 0.0002,
) -> QuantReport:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(csv_path)
    required = {"close"}
    if not required.issubset(df.columns):
        raise ValueError("CSV must include at least a 'close' column")

    close = df["close"].astype(float)
    returns = close.pct_change().fillna(0.0)

    # Baseline signal: momentum proxy (replace with Architect strategy wiring later)
    signal = np.where(returns.rolling(14).mean().fillna(0) > 0, 1, 0)

    trade_flag = np.abs(np.diff(np.insert(signal, 0, signal[0])))
    costs = trade_flag * (fee_pct + slippage_pct)
    strat_returns = signal * returns - costs

    equity = (1 + strat_returns).cumprod()
    net_profit_pct = float(equity.iloc[-1] - 1)
    mdd = _max_drawdown_from_equity(equity)
    vol = float(strat_returns.std()) or 1e-9
    sharpe = float((strat_returns.mean() / vol) * np.sqrt(365 * 24 * 60))

    gross_profit = float(strat_returns[strat_returns > 0].sum())
    gross_loss = abs(float(strat_returns[strat_returns < 0].sum())) or 1e-9
    pf = gross_profit / gross_loss
    wins = int((strat_returns > 0).sum())
    trades = int((trade_flag > 0).sum()) or 1
    win_rate = wins / trades

    verdict = "validated_for_demo" if sharpe > 2.0 and mdd < 0.015 else "hold"

    report = QuantReport(
        strategy_id=strategy_id,
        period={"start": str(df.index.min()), "end": str(df.index.max())},
        metrics=QuantMetrics(
            net_profit_pct=net_profit_pct,
            max_drawdown_pct=mdd,
            sharpe_ratio=sharpe,
            profit_factor=pf,
            win_rate=win_rate,
        ),
        verdict=verdict,
        observation="Initial vectorized baseline; replace signal with strategy contract input.",
    )
    return report


def save_report(report: QuantReport, out_path: str | Path) -> None:
    payload = asdict(report)
    payload["metrics"] = asdict(report.metrics)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(out_path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
