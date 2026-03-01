from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("executor_sync")


@dataclass
class SyncConfig:
    symbol: str
    sentiment_gate_path: Path
    runtime_state_path: Path
    pairs_registry_path: Path
    hysteresis_on: float = 80.0
    hysteresis_off: float = 75.0
    min_trade_usd: float = 100.0
    dry_run: bool = True
    post_only: bool = True
    exchange_testnet: bool = True


class DeltaExecutor:
    def __init__(self, cfg: SyncConfig) -> None:
        self.cfg = cfg
        self.tilt_active: dict[str, bool] = {}
        self.exchange = None

    def _read_json(self, p: Path, default: dict) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _ensure_exchange(self):
        if self.cfg.dry_run:
            return None
        if self.exchange is not None:
            return self.exchange
        import ccxt  # type: ignore

        self.exchange = ccxt.bybit(
            {
                "apiKey": os.getenv("BYBIT_API_KEY"),
                "secret": os.getenv("BYBIT_API_SECRET"),
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if self.cfg.exchange_testnet:
            self.exchange.set_sandbox_mode(True)
        return self.exchange

    def _target_delta_with_hysteresis(self, symbol: str, score: float, base_target_delta: float, on: float, off: float) -> float:
        active = self.tilt_active.get(symbol, False)
        if active:
            if score < off:
                self.tilt_active[symbol] = False
                return 0.0
            return base_target_delta
        if score > on:
            self.tilt_active[symbol] = True
            return base_target_delta
        return 0.0

    def _sync_symbol(self, symbol: str, score: float, base_target_delta: float, pair_cfg: dict) -> dict:
        hysteresis_buffer = float(pair_cfg.get("hysteresis_buffer", 5))
        on = float(pair_cfg.get("hysteresis_on", self.cfg.hysteresis_on))
        off = on - hysteresis_buffer if "hysteresis_off" not in pair_cfg else float(pair_cfg.get("hysteresis_off"))
        min_trade_usd = float(pair_cfg.get("min_trade_usd", self.cfg.min_trade_usd))

        target_delta = self._target_delta_with_hysteresis(symbol, score, base_target_delta, on, off)

        current_price = float(pair_cfg.get("current_price", 0) or 0)
        total_capital = float(pair_cfg.get("capital_usdt", 10000) or 10000)
        weight = float(pair_cfg.get("weight", 1.0))
        if current_price <= 0:
            return {"ok": False, "symbol": symbol, "reason": "missing_price", "target_delta": target_delta}

        target_notional = total_capital * weight * target_delta
        if target_notional < min_trade_usd:
            return {"ok": True, "symbol": symbol, "action": "skip_small_notional", "target_delta": target_delta}

        if self.cfg.dry_run:
            from src.simulator import DryRunSimulator

            sim = DryRunSimulator(Path(__file__).resolve().parents[1])
            side = "buy" if target_delta > 0 else "sell"
            qty = target_notional / current_price
            trade = sim.simulate_order(symbol, side, qty, current_price, order_type="limit")
            LOG.info("dry_run sync | %s score=%.2f target_delta=%.3f notional=%.2f", symbol, score, target_delta, target_notional)
            return {
                "ok": True,
                "symbol": symbol,
                "action": "dry_run_sync",
                "target_delta": target_delta,
                "notional": target_notional,
                "sim_trade": trade,
            }

        ex = self._ensure_exchange()
        side = "buy" if target_delta > 0 else "sell"
        amount = target_notional / current_price
        params = {"postOnly": self.cfg.post_only, "timeInForce": "PostOnly"} if self.cfg.post_only else {}
        ex.create_order(symbol, "limit" if self.cfg.post_only else "market", side, amount, current_price, params)
        return {"ok": True, "symbol": symbol, "action": "order_submitted", "target_delta": target_delta, "amount": amount}

    def sync_to_target_delta(self) -> dict:
        gate = self._read_json(self.cfg.sentiment_gate_path, {"score": 50})
        runtime = self._read_json(self.cfg.runtime_state_path, {"hybrid": {}})
        registry = self._read_json(self.cfg.pairs_registry_path, {})

        scores = gate.get("scores") if isinstance(gate.get("scores"), dict) else {}
        hybrid_map = runtime.get("hybrid") if isinstance(runtime.get("hybrid"), dict) else {}

        results = {}
        for symbol, cfg in registry.items():
            if not bool(cfg.get("enabled", True)):
                continue

            score = float(scores.get(symbol, gate.get("score", 50)))
            base_target_delta = float((hybrid_map.get(symbol) or {}).get("target_delta", 0.0))
            cfg = {**cfg, "capital_usdt": gate.get("capital_usdt", 10000), "current_price": gate.get("prices", {}).get(symbol, gate.get("current_price", 0))}
            results[symbol] = self._sync_symbol(symbol, score, base_target_delta, cfg)
            time.sleep(0.5)

        return {"ok": True, "results": results}
