from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("executor_sync")


@dataclass
class SyncConfig:
    symbol: str
    sentiment_gate_path: Path
    runtime_state_path: Path
    hysteresis_on: float = 80.0
    hysteresis_off: float = 75.0
    min_trade_usd: float = 100.0
    dry_run: bool = True
    post_only: bool = True
    exchange_testnet: bool = True


class DeltaExecutor:
    def __init__(self, cfg: SyncConfig) -> None:
        self.cfg = cfg
        self.tilt_active = False
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

    def _target_delta_with_hysteresis(self, score: float, base_target_delta: float) -> float:
        if self.tilt_active:
            if score < self.cfg.hysteresis_off:
                self.tilt_active = False
                return 0.0
            return base_target_delta
        if score > self.cfg.hysteresis_on:
            self.tilt_active = True
            return base_target_delta
        return 0.0

    def sync_to_target_delta(self) -> dict:
        gate = self._read_json(self.cfg.sentiment_gate_path, {"score": 50})
        runtime = self._read_json(self.cfg.runtime_state_path, {"hybrid": {"target_delta": 0.0}})

        score = float(gate.get("score", 50))
        base_target_delta = float((runtime.get("hybrid") or {}).get("target_delta", 0.0))
        target_delta = self._target_delta_with_hysteresis(score, base_target_delta)

        # quantity proxy from current price + nominal capital
        current_price = float(gate.get("current_price", 0) or 0)
        total_capital = float(gate.get("capital_usdt", 1000) or 1000)
        if current_price <= 0:
            return {"ok": False, "reason": "missing_price", "target_delta": target_delta}

        target_notional = total_capital * target_delta
        if target_notional < self.cfg.min_trade_usd:
            return {"ok": True, "action": "skip_small_notional", "target_delta": target_delta}

        if self.cfg.dry_run:
            LOG.info("dry_run sync | score=%.2f target_delta=%.3f notional=%.2f", score, target_delta, target_notional)
            return {"ok": True, "action": "dry_run_sync", "target_delta": target_delta, "notional": target_notional}

        ex = self._ensure_exchange()
        side = "buy" if target_delta > 0 else "sell"
        amount = target_notional / current_price
        params = {"postOnly": self.cfg.post_only, "timeInForce": "PostOnly"} if self.cfg.post_only else {}
        ex.create_order(self.cfg.symbol, "limit" if self.cfg.post_only else "market", side, amount, current_price, params)
        return {"ok": True, "action": "order_submitted", "target_delta": target_delta, "amount": amount}
