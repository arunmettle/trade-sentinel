#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.track_a_funding_arb import simulate_funding_arb


def read_funding(path: str):
    vals = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                vals.append(float(row["fundingRate"]))
            except Exception:
                continue
    return vals


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Track A funding arb simulation")
    ap.add_argument("--funding-csv", required=True)
    ap.add_argument("--out", default="reports/track_a_backtest.json")
    args = ap.parse_args()

    fr = read_funding(args.funding_csv)
    res = simulate_funding_arb(fr)
    payload = {
        "strategy": "track_a_funding_arb",
        "samples": len(fr),
        "net_yield_pct": res.net_yield_pct,
        "sharpe_ratio": res.sharpe_ratio,
        "max_drawdown_pct": res.max_drawdown_pct,
        "rebalance_count": res.rebalance_count,
        "gate": "pass" if res.sharpe_ratio >= 2.5 and res.max_drawdown_pct <= 0.03 else "fail",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
