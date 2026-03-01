from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.sentiment_agent import compute_market_pulse, write_gate

LOG = logging.getLogger("orchestrator")


@dataclass
class RuntimeConfig:
    loop_seconds: int
    strategy_path: Path
    sentiment_gate_path: Path


def load_runtime_config(base_dir: Path) -> RuntimeConfig:
    with (base_dir / "config" / "live_config.json").open("r", encoding="utf-8") as f:
        live = json.load(f)

    loop_seconds = int(live.get("runtime", {}).get("orchestrator_loop_seconds", 60))
    strategy_rel = live.get("paths", {}).get("strategy", "config/live_strategy.json")
    sentiment_rel = live.get("paths", {}).get("sentiment_gate", "config/sentiment_gate.json")

    return RuntimeConfig(
        loop_seconds=loop_seconds,
        strategy_path=base_dir / strategy_rel,
        sentiment_gate_path=base_dir / sentiment_rel,
    )


def load_strategy(strategy_path: Path) -> dict:
    with strategy_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_trade_mode(strategy: dict, sentiment_gate: dict) -> dict:
    regime = strategy.get("regime", "C")
    status = strategy.get("status", "flat")
    allow_by_sentiment = bool(sentiment_gate.get("allow_trading", False))

    if regime == "C" or status in {"flat", "paused"} or not allow_by_sentiment:
        return {"mode": "FLAT", "allow_new_trades": False}
    return {"mode": "ACTIVE", "allow_new_trades": True}


def write_runtime_state(base_dir: Path, payload: dict) -> None:
    p = base_dir / "logs" / "runtime_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def run_once(base_dir: Path, headlines: list[str] | None = None) -> dict:
    cfg = load_runtime_config(base_dir)
    strategy = load_strategy(cfg.strategy_path)
    gate = compute_market_pulse(headlines or [])
    write_gate(gate, cfg.sentiment_gate_path)
    mode = resolve_trade_mode(strategy, gate)

    state = {
        "strategy_regime": strategy.get("regime"),
        "strategy_status": strategy.get("status"),
        "sentiment": gate,
        "trade_mode": mode,
    }
    write_runtime_state(base_dir, state)
    return state


def run_loop(base_dir: Path) -> None:
    cfg = load_runtime_config(base_dir)
    LOG.info("orchestrator started | loop=%ss", cfg.loop_seconds)
    while True:
        state = run_once(base_dir)
        LOG.info("trade_mode=%s allow_new_trades=%s", state["trade_mode"]["mode"], state["trade_mode"]["allow_new_trades"])
        time.sleep(cfg.loop_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = Path(__file__).resolve().parents[1]
    run_loop(root)
