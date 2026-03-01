#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import ccxt

from src.validators import validate_bybit_netting_mode


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    live = json.loads((base / "config" / "live_config.json").read_text(encoding="utf-8"))
    symbol = live.get("symbol", "BTC/USDT:USDT")

    key = os.getenv("BYBIT_API_KEY")
    sec = os.getenv("BYBIT_API_SECRET")
    if not key or not sec:
        print(json.dumps({"ok": False, "reason": "missing_api_keys"}, indent=2))
        return 1

    ex = ccxt.bybit(
        {
            "apiKey": key,
            "secret": sec,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )
    if bool(live.get("exchange", {}).get("testnet", True)):
        ex.set_sandbox_mode(True)

    netting_ok = validate_bybit_netting_mode(ex, symbol)
    out = {"ok": bool(netting_ok), "symbol": symbol, "netting_mode_ok": bool(netting_ok)}
    print(json.dumps(out, indent=2))
    return 0 if netting_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
