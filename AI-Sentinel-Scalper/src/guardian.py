"""Guardian module (Phase 1 skeleton).

Safety-critical watchdog for equity lock and emergency flatten.
This initial version is intentionally conservative and dry-run friendly.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOG = logging.getLogger("guardian")


@dataclass
class GuardianConfig:
    symbol: str
    loop_seconds: float
    dry_run: bool
    daily_equity_lock_pct: float
    state_path: Path


class Guardian:
    def __init__(self, config: GuardianConfig) -> None:
        self.config = config
        self.start_equity: float | None = None
        self.active = True

    def startup_self_check(self) -> None:
        """Basic environment and config validation.

        Exchange/API connectivity checks are TODO for next iteration.
        """
        if self.config.daily_equity_lock_pct <= 0:
            raise ValueError("daily_equity_lock_pct must be positive")
        if self.config.loop_seconds <= 0:
            raise ValueError("loop_seconds must be positive")
        LOG.info("startup check ok")

    def fetch_total_equity(self) -> float:
        """Fetch current total equity.

        TODO: Replace stub with ccxt/bybit fetch_balance implementation.
        """
        # Stub to keep skeleton runnable without exchange credentials.
        return float(os.getenv("GUARDIAN_STUB_EQUITY", "1000"))

    def compute_drawdown(self, current_equity: float) -> float:
        if self.start_equity is None:
            raise RuntimeError("start_equity is not initialized")
        return max(0.0, (self.start_equity - current_equity) / self.start_equity)

    def emergency_flatten(self, reason: str) -> None:
        """Cancel all orders + close all positions (or simulate in dry run)."""
        LOG.warning("EMERGENCY FLATTEN TRIGGERED: %s", reason)
        if self.config.dry_run:
            LOG.warning("dry_run=true -> simulated cancel/flatten only")
            self.active = False
            return

        # TODO: Implement exchange calls:
        # 1) cancel all open orders
        # 2) market-close all open positions with reduce-only
        # 3) halt executor process or set kill flag
        self.active = False

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
                }
                self.persist_state(state)
                LOG.info("monitor | equity=%.4f drawdown=%.4f", current, dd)

                if dd >= self.config.daily_equity_lock_pct:
                    self.emergency_flatten(
                        f"drawdown {dd:.4f} >= threshold {self.config.daily_equity_lock_pct:.4f}"
                    )
                    break

                time.sleep(self.config.loop_seconds)
            except Exception as exc:
                LOG.exception("guardian loop error: %s", exc)
                time.sleep(max(1.0, self.config.loop_seconds))


def load_config(base_dir: Path) -> GuardianConfig:
    live_cfg_path = base_dir / "config" / "live_config.json"
    if not live_cfg_path.exists():
        # fallback for first run
        live_cfg_path = base_dir / "config" / "live_config.example.json"

    risk_cfg_path = base_dir / "config" / "risk_limits.json"

    with live_cfg_path.open("r", encoding="utf-8") as f:
        live = json.load(f)
    with risk_cfg_path.open("r", encoding="utf-8") as f:
        risk = json.load(f)

    return GuardianConfig(
        symbol=live.get("symbol", "BTC/USDT:USDT"),
        loop_seconds=float(live.get("runtime", {}).get("guardian_loop_seconds", 1)),
        dry_run=bool(live.get("runtime", {}).get("dry_run", True)),
        daily_equity_lock_pct=float(risk.get("daily_equity_lock_pct", 0.02)),
        state_path=base_dir / live.get("paths", {}).get("guardian_state", "logs/guardian_state.json"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root)
    Guardian(cfg).run()
