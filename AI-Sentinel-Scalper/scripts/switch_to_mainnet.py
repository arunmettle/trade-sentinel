#!/usr/bin/env python3
from __future__ import annotations

import getpass
from pathlib import Path


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    env_path = base / ".env"

    key = input("Enter BYBIT mainnet API key: ").strip()
    secret = getpass.getpass("Enter BYBIT mainnet API secret: ").strip()

    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    kv = {
        "BYBIT_API_KEY": key,
        "BYBIT_API_SECRET": secret,
        "BYBIT_TESTNET": "false",
        "BYBIT_BASE_URL": "https://api.bybit.com",
        "TRAINING_WHEELS_MAX_POSITION_USD": "100",
    }

    out = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    out.update(kv)

    env_text = "\n".join([f"{k}={v}" for k, v in out.items()]) + "\n"
    env_path.write_text(env_text, encoding="utf-8")
    print(f"Updated {env_path}")
    print("Mainnet settings staged with training wheels cap = $100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
