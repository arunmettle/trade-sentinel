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
    ap = argparse.ArgumentParser(description="Fetch Bybit funding-rate history")
    ap.add_argument("--symbol", default="BTC/USDT:USDT")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()

    ex = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "future"}})
    if args.testnet:
        ex.set_sandbox_mode(True)

    rows = ex.fetch_funding_rate_history(args.symbol, limit=args.limit)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "fundingRate"])
        for r in rows:
            ts = r.get("timestamp")
            fr = r.get("fundingRate")
            if ts is None or fr is None:
                continue
            w.writerow([iso(int(ts)), fr])

    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
