#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.regime_backtest import run_regime_backtest, save_results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/btcusdt_1m_30d_real.csv")
    ap.add_argument("--out-json", default="reports/regime_backtest.json")
    ap.add_argument("--out-md", default="reports/regime_backtest.md")
    args = ap.parse_args()

    results = run_regime_backtest(args.csv)
    save_results(results, Path(args.out_json), Path(args.out_md))
    print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
