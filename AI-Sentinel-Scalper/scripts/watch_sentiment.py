#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.executor_sync import DeltaExecutor, SyncConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
LOG = logging.getLogger("watch_sentiment")


@dataclass
class RateGuard:
    min_sync_seconds: int = 30
    override_score_jump: float = 20.0
    last_sync_ts: float = 0.0
    last_score: float = 50.0

    def should_sync(self, score: float, now_ts: float) -> bool:
        jump = abs(score - self.last_score)
        elapsed = now_ts - self.last_sync_ts
        return elapsed >= self.min_sync_seconds or jump >= self.override_score_jump

    def mark_synced(self, score: float, now_ts: float) -> None:
        self.last_score = score
        self.last_sync_ts = now_ts


def load_cfg(base: Path) -> SyncConfig:
    live = json.loads((base / "config" / "live_config.json").read_text(encoding="utf-8"))
    return SyncConfig(
        symbol=live.get("symbol", "BTC/USDT:USDT"),
        sentiment_gate_path=base / live.get("paths", {}).get("sentiment_gate", "config/sentiment_gate.json"),
        runtime_state_path=base / live.get("paths", {}).get("runtime_state", "logs/runtime_state.json"),
        pairs_registry_path=base / live.get("paths", {}).get("pairs_registry", "config/pairs_registry.json"),
        hysteresis_on=float(live.get("hybrid", {}).get("hysteresis_on", 80)),
        hysteresis_off=float(live.get("hybrid", {}).get("hysteresis_off", 75)),
        min_trade_usd=float(live.get("hybrid", {}).get("min_trade_usd", 100)),
        dry_run=bool(live.get("runtime", {}).get("dry_run", True)),
        post_only=bool(live.get("execution", {}).get("order_type_preference", "").startswith("limit_post_only")),
        exchange_testnet=bool(live.get("exchange", {}).get("testnet", True)),
    )


def read_score(path: Path) -> float:
    try:
        return float(json.loads(path.read_text(encoding="utf-8")).get("score", 50))
    except Exception:
        return 50.0


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    cfg = load_cfg(base)
    executor = DeltaExecutor(cfg)
    guard = RateGuard()

    def maybe_sync():
        score = read_score(cfg.sentiment_gate_path)
        now_ts = time.time()
        if guard.should_sync(score, now_ts):
            LOG.info(executor.sync_to_target_delta())
            guard.mark_synced(score, now_ts)

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        LOG.warning("watchdog not installed; falling back to mtime polling")
        last_mtime = 0.0
        while True:
            p = cfg.sentiment_gate_path
            m = p.stat().st_mtime if p.exists() else 0.0
            if m > last_mtime:
                last_mtime = m
                maybe_sync()
            time.sleep(1)

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if str(cfg.sentiment_gate_path) in event.src_path:
                maybe_sync()

    obs = Observer()
    obs.schedule(Handler(), str(cfg.sentiment_gate_path.parent), recursive=False)
    obs.start()
    LOG.info("watching %s", cfg.sentiment_gate_path)
    try:
        while True:
            time.sleep(1)
    finally:
        obs.stop()
        obs.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
