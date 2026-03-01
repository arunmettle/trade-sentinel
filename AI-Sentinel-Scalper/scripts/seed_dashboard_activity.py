#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from src.executor_sync import DeltaExecutor, SyncConfig
from src.hybrid_manager import HybridManager


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    live = json.loads((base / "config" / "live_config.json").read_text(encoding="utf-8"))

    sentiment_path = base / live["paths"]["sentiment_gate"]
    runtime_path = base / live["paths"]["runtime_state"]
    registry_path = base / live["paths"]["pairs_registry"]

    cfg = SyncConfig(
        symbol=live.get("symbol", "BTC/USDT:USDT"),
        sentiment_gate_path=sentiment_path,
        runtime_state_path=runtime_path,
        pairs_registry_path=registry_path,
        hysteresis_on=float(live.get("hybrid", {}).get("hysteresis_on", 80)),
        hysteresis_off=float(live.get("hybrid", {}).get("hysteresis_off", 75)),
        min_trade_usd=float(live.get("hybrid", {}).get("min_trade_usd", 100)),
        dry_run=True,
        post_only=True,
        exchange_testnet=bool(live.get("exchange", {}).get("testnet", True)),
    )

    ex = DeltaExecutor(cfg)

    gate = {
        "score": 84,
        "scores": {
            "BTC/USDT:USDT": 86,
            "SOL/USDT:USDT": 90,
            "LINK/USDT:USDT": 78,
        },
        "prices": {
            "BTC/USDT:USDT": 66000,
            "SOL/USDT:USDT": 142,
            "LINK/USDT:USDT": 20.2,
        },
        "capital_usdt": 10000,
        "allow_trading": True,
    }
    sentiment_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")

    hybrid = HybridManager(sentiment_path, registry_path).compute_targets()
    runtime = {
        "strategy_regime": "A",
        "strategy_status": "active",
        "trade_mode": {"mode": "ACTIVE", "allow_new_trades": True},
        "hybrid": hybrid,
        "regime_advisory": {
            "active_regime": "HUNT",
            "adr_ratio": 1.02,
            "proposed_overrides": {"hurdle_multiplier": 2.0, "min_trade_usd": 300},
            "advisory_only": True,
        },
    }
    runtime_path.write_text(json.dumps(runtime, indent=2), encoding="utf-8")

    print(ex.sync_to_target_delta())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
