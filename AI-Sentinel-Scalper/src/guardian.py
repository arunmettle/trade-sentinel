"""Guardian module (M2).

Safety-critical watchdog:
- captures baseline equity
- monitors drawdown
- triggers kill-switch (cancel orders + flatten positions)
- persists machine-readable state for dashboard/orchestrator
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

LOG = logging.getLogger("guardian")


@dataclass
class GuardianConfig:
    symbol: str
    loop_seconds: float
    dry_run: bool
    daily_equity_lock_pct: float
    state_path: Path
    exchange_name: str = "bybit"
    exchange_default_type: str = "future"
    exchange_testnet: bool = True
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0


class Guardian:
    def __init__(self, config: GuardianConfig, exchange: Any | None = None) -> None:
        self.config = config
        self.exchange = exchange
        self.start_equity: float | None = None
        self.active = True

    def startup_self_check(self) -> None:
        if self.config.daily_equity_lock_pct <= 0:
            raise ValueError("daily_equity_lock_pct must be positive")
        if self.config.loop_seconds <= 0:
            raise ValueError("loop_seconds must be positive")
        if self.config.max_retries < 1:
            raise ValueError("max_retries must be >= 1")

        if not self.config.dry_run:
            if not os.getenv("BYBIT_API_KEY") or not os.getenv("BYBIT_API_SECRET"):
                raise EnvironmentError("BYBIT_API_KEY and BYBIT_API_SECRET are required when dry_run=false")
            self._ensure_exchange()
            _ = self._retry(self._fetch_total_equity_live)

        LOG.info("startup check ok")

    def _ensure_exchange(self) -> None:
        if self.exchange is not None:
            return
        try:
            import ccxt  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ccxt is required for live mode. Install with: pip install ccxt") from exc

        if self.config.exchange_name.lower() != "bybit":
            raise ValueError("Only bybit exchange is supported in phase 1")

        self.exchange = ccxt.bybit(
            {
                "apiKey": os.getenv("BYBIT_API_KEY"),
                "secret": os.getenv("BYBIT_API_SECRET"),
                "enableRateLimit": True,
                "options": {
                    "defaultType": self.config.exchange_default_type,
                },
            }
        )
        if self.config.exchange_testnet:
            self.exchange.set_sandbox_mode(True)

    def _retry(self, fn, *args, **kwargs):
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                LOG.warning("attempt %s/%s failed: %s", attempt, self.config.max_retries, exc)
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds)
        raise RuntimeError(f"operation failed after {self.config.max_retries} retries") from last_exc

    def _fetch_total_equity_live(self) -> float:
        self._ensure_exchange()
        bal = self.exchange.fetch_balance()
        usdt_total = bal.get("total", {}).get("USDT")
        if usdt_total is None:
            raise RuntimeError("USDT total equity not found in balance response")
        return float(usdt_total)

    def fetch_total_equity(self) -> float:
        if self.config.dry_run:
            return float(os.getenv("GUARDIAN_STUB_EQUITY", "1000"))
        return float(self._retry(self._fetch_total_equity_live))

    def compute_drawdown(self, current_equity: float) -> float:
        if self.start_equity is None:
            raise RuntimeError("start_equity is not initialized")
        return max(0.0, (self.start_equity - current_equity) / self.start_equity)

    def _cancel_all_orders(self) -> None:
        self._ensure_exchange()
        self.exchange.cancel_all_orders(self.config.symbol)

    def _close_all_positions(self) -> None:
        self._ensure_exchange()
        positions = self.exchange.fetch_positions([self.config.symbol])
        for pos in positions or []:
            contracts = float(pos.get("contracts") or 0)
            side = str(pos.get("side") or "").lower()
            if contracts <= 0:
                continue
            close_side = "sell" if side == "long" else "buy"
            self.exchange.create_order(
                symbol=self.config.symbol,
                type="market",
                side=close_side,
                amount=contracts,
                params={"reduceOnly": True},
            )

    def emergency_flatten(self, reason: str) -> None:
        LOG.warning("EMERGENCY FLATTEN TRIGGERED: %s", reason)
        if self.config.dry_run:
            LOG.warning("dry_run=true -> simulated cancel/flatten only")
            self.active = False
            self.persist_state({"ts": int(time.time()), "event": "killswitch", "dry_run": True, "reason": reason})
            return

        self._retry(self._cancel_all_orders)
        self._retry(self._close_all_positions)
        self.active = False
        self.persist_state({"ts": int(time.time()), "event": "killswitch", "dry_run": False, "reason": reason})

    def persist_state(self, payload: dict[str, Any]) -> None:
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.state_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def run(self) -> None:
        self.startup_self_check()
        self.start_equity = self.fetch_total_equity()
        LOG.info("guardian started | symbol=%s | start_equity=%.4f", self.config.symbol, self.start_equity)

        while self.active:
            try:
                current = self.fetch_total_equity()
                dd = self.compute_drawdown(current)
                state = {
                    "ts": int(time.time()),
                    "symbol": self.config.symbol,
                    "start_equity": self.start_equity,
                    "current_equity": current,
                    "drawdown": dd,
                    "lock_threshold": self.config.daily_equity_lock_pct,
                    "dry_run": self.config.dry_run,
                    "status": "monitoring",
                }
                self.persist_state(state)
                LOG.info("monitor | equity=%.4f drawdown=%.4f", current, dd)

                if dd >= self.config.daily_equity_lock_pct:
                    self.emergency_flatten(
                        f"drawdown {dd:.4f} >= threshold {self.config.daily_equity_lock_pct:.4f}"
                    )
                    break

                time.sleep(self.config.loop_seconds)
            except Exception as exc:  # noqa: BLE001
                LOG.exception("guardian loop error: %s", exc)
                time.sleep(max(1.0, self.config.loop_seconds))


def load_config(base_dir: Path) -> GuardianConfig:
    live_cfg_path = base_dir / "config" / "live_config.json"
    if not live_cfg_path.exists():
        live_cfg_path = base_dir / "config" / "live_config.example.json"

    with live_cfg_path.open("r", encoding="utf-8") as f:
        live = json.load(f)

    risk_path = base_dir / live.get("paths", {}).get("risk_limits", "config/risk_limits.json")
    with risk_path.open("r", encoding="utf-8") as f:
        risk = json.load(f)

    return GuardianConfig(
        symbol=live.get("symbol", "BTC/USDT:USDT"),
        loop_seconds=float(live.get("runtime", {}).get("guardian_loop_seconds", 1)),
        dry_run=bool(live.get("runtime", {}).get("dry_run", True)),
        daily_equity_lock_pct=float(risk.get("daily_equity_lock_pct", 0.02)),
        state_path=base_dir / live.get("paths", {}).get("guardian_state", "logs/guardian_state.json"),
        exchange_name=str(live.get("exchange", {}).get("name", "bybit")),
        exchange_default_type=str(live.get("exchange", {}).get("defaultType", "future")),
        exchange_testnet=bool(live.get("exchange", {}).get("testnet", True)),
        max_retries=int(live.get("runtime", {}).get("max_retries", 3)),
        retry_backoff_seconds=float(live.get("runtime", {}).get("retry_backoff_seconds", 1.0)),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root)
    Guardian(cfg).run()
