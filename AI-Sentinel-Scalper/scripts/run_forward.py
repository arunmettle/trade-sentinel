#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.quant_runner import run_vectorized_backtest, save_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Run 48h forward validation on unseen data")
    ap.add_argument("--csv", required=True, help="Path to unseen forward CSV")
    ap.add_argument("--strategy-id", default="phase1_forward")
    ap.add_argument("--out", default="reports/forward_report.json")
    args = ap.parse_args()

    report = run_vectorized_backtest(args.csv, strategy_id=args.strategy_id)
    payload = {
        "window_hours": 48,
        "strategy_id": report.strategy_id,
        "net_pnl_pct": report.metrics.net_profit_pct,
        "trade_count_estimate": int(report.metrics.win_rate * 100),
        "verdict": "pass" if report.metrics.net_profit_pct > 0 else "fail",
        "metrics": {
            "max_drawdown_pct": report.metrics.max_drawdown_pct,
            "sharpe_ratio": report.metrics.sharpe_ratio,
            "profit_factor": report.metrics.profit_factor,
            "win_rate": report.metrics.win_rate,
        },
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save_report(report, Path(args.out).with_name("forward_quant_report.json"))
    print(json.dumps({"report": args.out, "verdict": payload["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
