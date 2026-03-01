#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.gate_evaluator import evaluate_promotion
from src.main import run_once


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run demo soak loop and emit demo report")
    ap.add_argument("--minutes", type=int, default=1440, help="Soak duration in minutes (default 24h)")
    ap.add_argument("--interval-seconds", type=int, default=60)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--out", default="reports/demo_report.json")
    args = ap.parse_args()

    base = Path(args.base_dir).resolve()
    start = time.time()
    end = start + args.minutes * 60

    samples = 0
    while time.time() < end:
        run_once(base)
        samples += 1
        time.sleep(max(1, args.interval_seconds))

    quant = load_json(base / "reports" / "quant_report.json")
    backtest_pnl = ((quant.get("metrics") or {}).get("net_profit_pct")) or 0.0

    runtime = load_json(base / "logs" / "runtime_state.json")
    guardian = load_json(base / "logs" / "guardian_state.json")

    # Placeholder demo pnl proxy until live execution ledger is wired:
    # prefer guardian equity delta if present, else 0.
    demo_pnl = 0.0
    if guardian.get("start_equity") and guardian.get("current_equity"):
        s = float(guardian["start_equity"])
        c = float(guardian["current_equity"])
        if s != 0:
            demo_pnl = (c - s) / s

    decision = evaluate_promotion(backtest_pnl, demo_pnl)

    payload = {
        "window_minutes": args.minutes,
        "environment": "bybit_demo_uta",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "net_pnl_pct": demo_pnl,
        "backtest_expected_pnl_pct": backtest_pnl,
        "drift_pct": abs(demo_pnl - backtest_pnl) / (abs(backtest_pnl) if abs(backtest_pnl) > 1e-9 else 1e-9),
        "promotion_decision": decision,
        "runtime_trade_mode": (runtime.get("trade_mode") or {}).get("mode"),
        "guardian_snapshot": {
            "drawdown": guardian.get("drawdown"),
            "lock_threshold": guardian.get("lock_threshold"),
            "dry_run": guardian.get("dry_run"),
        },
        "notes": "Demo soak orchestration validated. Replace pnl proxy with real trade ledger integration for production decisioning.",
    }

    out = base / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "samples": samples, "promotion_decision": decision}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
