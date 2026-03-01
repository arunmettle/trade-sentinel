#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

import ccxt


def main() -> int:
    ap = argparse.ArgumentParser(description="List balances below a USD threshold (dust report)")
    ap.add_argument("--threshold-usd", type=float, default=1.0)
    args = ap.parse_args()

    key = os.getenv("BYBIT_API_KEY")
    secret = os.getenv("BYBIT_API_SECRET")
    if not key or not secret:
        raise SystemExit("Missing BYBIT_API_KEY/BYBIT_API_SECRET")

    ex = ccxt.bybit({"apiKey": key, "secret": secret, "enableRateLimit": True})
    if os.getenv("BYBIT_TESTNET", "true").lower() in {"1", "true", "yes"}:
        ex.set_sandbox_mode(True)

    bal = ex.fetch_balance()
    total = bal.get("total") or {}
    dust = []
    for coin, qty in total.items():
        try:
            q = float(qty or 0)
        except Exception:
            continue
        if q <= 0:
            continue
        # best-effort valuation skip for USDT
        usd = q if coin == "USDT" else None
        if usd is not None and usd < args.threshold_usd:
            dust.append({"coin": coin, "qty": q, "approx_usd": usd})

    print(json.dumps({"threshold_usd": args.threshold_usd, "dust": dust}, indent=2))
    print("Note: auto-convert endpoint integration may vary; this script reports dust candidates safely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
