#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import ccxt


def main() -> int:
    key = os.getenv("BYBIT_API_KEY")
    sec = os.getenv("BYBIT_API_SECRET")
    if not key or not sec:
        raise SystemExit("BYBIT_API_KEY/BYBIT_API_SECRET missing")

    ex = ccxt.bybit(
        {
            "apiKey": key,
            "secret": sec,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )
    ex.set_sandbox_mode(True)

    bal = ex.fetch_balance()
    usdt = (bal.get("total") or {}).get("USDT")
    print(json.dumps({"ok": True, "testnet": True, "usdt_total": usdt}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
