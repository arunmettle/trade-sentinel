#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import ccxt


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Bybit OHLCV candles to CSV")
    ap.add_argument("--symbol", default="BTC/USDT:USDT")
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()

    ex = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "future"}})
    if args.testnet:
        ex.set_sandbox_mode(True)

    limit = 1000
    need = args.minutes
    all_rows = []

    # fetch most recent candles in reverse windows
    now = ex.milliseconds()
    since = now - (need + 10) * 60 * 1000

    while len(all_rows) < need:
        batch = ex.fetch_ohlcv(args.symbol, timeframe=args.timeframe, since=since, limit=limit)
        if not batch:
            break
        all_rows.extend(batch)
        since = batch[-1][0] + 60 * 1000
        if len(batch) < limit:
            break

    rows = all_rows[-need:]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([iso(r[0]), r[1], r[2], r[3], r[4], r[5]])

    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
