from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.hybrid_manager import HybridManager
from src.regime_switcher import advisory_snapshot
from src.sentiment_agent import compute_market_pulse, write_gate
from src.validators import validate_bybit_netting_mode

LOG = logging.getLogger("orchestrator")


@dataclass
class RuntimeConfig:
    loop_seconds: int
    strategy_path: Path
    sentiment_gate_path: Path
    pairs_registry_path: Path


def load_runtime_config(base_dir: Path) -> RuntimeConfig:
    with (base_dir / "config" / "live_config.json").open("r", encoding="utf-8") as f:
        live = json.load(f)

    loop_seconds = int(live.get("runtime", {}).get("orchestrator_loop_seconds", 60))
    strategy_rel = live.get("paths", {}).get("strategy", "config/live_strategy.json")
    sentiment_rel = live.get("paths", {}).get("sentiment_gate", "config/sentiment_gate.json")
    registry_rel = live.get("paths", {}).get("pairs_registry", "config/pairs_registry.json")

    return RuntimeConfig(
        loop_seconds=loop_seconds,
        strategy_path=base_dir / strategy_rel,
        sentiment_gate_path=base_dir / sentiment_rel,
        pairs_registry_path=base_dir / registry_rel,
    )


def load_strategy(strategy_path: Path) -> dict:
    with strategy_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_registry(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_trade_mode(strategy: dict, sentiment_gate: dict) -> dict:
    regime = strategy.get("regime", "C")
    status = strategy.get("status", "flat")
    allow_by_sentiment = bool(sentiment_gate.get("allow_trading", False))

    if regime == "C" or status in {"flat", "paused"} or not allow_by_sentiment:
        return {"mode": "FLAT", "allow_new_trades": False}
    return {"mode": "ACTIVE", "allow_new_trades": True}


def write_runtime_state(base_dir: Path, payload: dict) -> None:
    p = base_dir / "logs" / "runtime_state.json"
    tmp = base_dir / "logs" / "runtime_state.json.tmp"
    p.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(p)


def run_once(base_dir: Path, headlines: list[str] | None = None) -> dict:
    cfg = load_runtime_config(base_dir)
    strategy = load_strategy(cfg.strategy_path)
    registry = load_registry(cfg.pairs_registry_path)

    gate = compute_market_pulse(headlines or [])
    if registry:
        # phase-1 multi-pair: same score fanout; can be replaced by per-symbol model later
        gate["scores"] = {symbol: gate.get("score", 50) for symbol, pcfg in registry.items() if pcfg.get("enabled", True)}
    write_gate(gate, cfg.sentiment_gate_path)

    mode = resolve_trade_mode(strategy, gate)

    hybrid = HybridManager(cfg.sentiment_gate_path, cfg.pairs_registry_path).compute_targets()

    regime_advisory = advisory_snapshot(base_dir)

    state = {
        "strategy_regime": strategy.get("regime"),
        "strategy_status": strategy.get("status"),
        "sentiment": gate,
        "trade_mode": mode,
        "hybrid": hybrid,
        "regime_advisory": regime_advisory,
    }
    write_runtime_state(base_dir, state)
    return state


def run_loop(base_dir: Path) -> None:
    cfg = load_runtime_config(base_dir)

    # Netting mode preflight (required for hybrid delta-tilt semantics)
    with (base_dir / "config" / "live_config.json").open("r", encoding="utf-8") as f:
        live = json.load(f)
    dry_run = bool(live.get("runtime", {}).get("dry_run", True))
    symbol = live.get("symbol", "BTC/USDT:USDT")

    if not dry_run:
        import ccxt  # type: ignore

        ex = ccxt.bybit(
            {
                "apiKey": os.getenv("BYBIT_API_KEY"),
                "secret": os.getenv("BYBIT_API_SECRET"),
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if bool(live.get("exchange", {}).get("testnet", True)):
            ex.set_sandbox_mode(True)
        if not validate_bybit_netting_mode(ex, symbol):
            raise RuntimeError("Startup preflight failed: account must be in Netting/One-Way mode")

    LOG.info("orchestrator started | loop=%ss", cfg.loop_seconds)
    while True:
        state = run_once(base_dir)
        LOG.info(
            "trade_mode=%s allow_new_trades=%s pairs=%s",
            state["trade_mode"]["mode"],
            state["trade_mode"]["allow_new_trades"],
            len(state.get("hybrid", {})),
        )
        time.sleep(cfg.loop_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = Path(__file__).resolve().parents[1]
    run_loop(root)
