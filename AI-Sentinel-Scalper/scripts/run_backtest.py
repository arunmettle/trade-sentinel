#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.gate_evaluator import evaluate_backtest
from src.quant_runner import run_vectorized_backtest, save_report
from src.strategy_engine import load_strategy


def main() -> int:
    ap = argparse.ArgumentParser(description="Run backtest and emit quant report")
    ap.add_argument("--csv", required=True, help="Path to 1m OHLCV CSV (must include close)")
    ap.add_argument("--strategy-id", default="phase1_backtest")
    ap.add_argument("--out", default="reports/quant_report.json")
    ap.add_argument("--summary", default="reports/backtest_summary.md")
    ap.add_argument("--strategy", default="", help="Optional strategy JSON path")
    args = ap.parse_args()

    strategy = load_strategy(args.strategy) if args.strategy else None
    report = run_vectorized_backtest(args.csv, strategy_id=args.strategy_id, strategy=strategy)
    save_report(report, args.out)

    gate = evaluate_backtest(report.metrics.sharpe_ratio, report.metrics.max_drawdown_pct)
    summary = Path(args.summary)
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "\n".join(
            [
                "# Backtest Summary",
                f"- Strategy: {report.strategy_id}",
                f"- Net Profit: {report.metrics.net_profit_pct:.4f}",
                f"- Max Drawdown: {report.metrics.max_drawdown_pct:.4f}",
                f"- Sharpe: {report.metrics.sharpe_ratio:.4f}",
                f"- Profit Factor: {report.metrics.profit_factor:.4f}",
                f"- Win Rate: {report.metrics.win_rate:.4f}",
                f"- Gate: {gate}",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps({"report": args.out, "summary": args.summary, "gate": gate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
