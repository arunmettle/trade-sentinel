"""Guardian module (multi-pair aware).

Safety-critical watchdog:
- captures baseline equity
- monitors drawdown
- triggers kill-switch (cancel orders + flatten positions)
- performs emergency delta-drift rebalance for hybrid mode per active pair
- persists machine-readable state for dashboard/orchestrator
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.notifications import send_telegram_alert

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
    drift_deadzone: float = 0.01
    max_spread_for_rebalance: float = 0.001
    runtime_state_path: Path = Path("logs/runtime_state.json")
    rebalance_log_path: Path = Path("logs/rebalance_events.csv")
    pairs_registry_path: Path = Path("config/pairs_registry.json")


class Guardian:
    def __init__(self, config: GuardianConfig, exchange: Any | None = None) -> None:
        self.config = config
        self.exchange = exchange
        self.start_equity: float | None = None
        self.active = True
        self.high_drift_cycles: dict[str, int] = {}

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
        import ccxt  # type: ignore

        if self.config.exchange_name.lower() != "bybit":
            raise ValueError("Only bybit exchange is supported in phase 1")

        self.exchange = ccxt.bybit(
            {
                "apiKey": os.getenv("BYBIT_API_KEY"),
                "secret": os.getenv("BYBIT_API_SECRET"),
                "enableRateLimit": True,
                "options": {"defaultType": self.config.exchange_default_type},
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

    def calculate_drift(self, spot_qty: float, perp_qty: float, target_delta: float, total_equity: float) -> tuple[float, float, str | None]:
        """Return (actual_delta, drift, status_override).

        Safety guard: when account equity is effectively flat, avoid unstable ratio math.
        """
        if total_equity < 10.0:
            return 0.0, 0.0, "FLAT_LEGAL"

        if spot_qty <= 0:
            # no spot leg => treat as fully hedged drift not computable by ratio
            return 0.0, abs(0.0 - target_delta), "NO_SPOT_LEG"

        actual_delta = (spot_qty - perp_qty) / spot_qty
        drift = abs(actual_delta - target_delta)
        return actual_delta, drift, None

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
            self.active = False
            self.persist_state({"ts": int(time.time()), "event": "killswitch", "dry_run": True, "reason": reason})
            return

        self._retry(self._cancel_all_orders)
        self._retry(self._close_all_positions)
        self.active = False
        self.persist_state({"ts": int(time.time()), "event": "killswitch", "dry_run": False, "reason": reason})

    def _read_runtime_state(self) -> dict:
        if not self.config.runtime_state_path.exists():
            return {}
        try:
            return json.loads(self.config.runtime_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _read_registry(self) -> dict:
        if not self.config.pairs_registry_path.exists():
            return {self.config.symbol: {"enabled": True}}
        try:
            return json.loads(self.config.pairs_registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {self.config.symbol: {"enabled": True}}

    def _fetch_spot_and_perp_qty(self, symbol: str) -> tuple[float, float]:
        if self.config.dry_run:
            s = symbol.split("/")[0]
            spot = float(os.getenv(f"GUARDIAN_STUB_SPOT_QTY_{s}", os.getenv("GUARDIAN_STUB_SPOT_QTY", "1.0")))
            perp = float(os.getenv(f"GUARDIAN_STUB_PERP_QTY_{s}", os.getenv("GUARDIAN_STUB_PERP_QTY", "1.0")))
            return spot, perp

        self._ensure_exchange()
        bal = self.exchange.fetch_balance()
        base = symbol.split("/")[0]
        spot_qty = float((bal.get("total") or {}).get(base, 0) or 0)
        positions = self.exchange.fetch_positions([symbol])
        perp_qty = abs(float(positions[0].get("contracts") or 0)) if positions else 0.0
        return spot_qty, perp_qty

    def _fetch_spread(self, symbol: str) -> float:
        if self.config.dry_run:
            return float(os.getenv("GUARDIAN_STUB_SPREAD", "0.0002"))
        self._ensure_exchange()
        ob = self.exchange.fetch_order_book(symbol, limit=5)
        bid = float(ob["bids"][0][0]) if ob.get("bids") else 0
        ask = float(ob["asks"][0][0]) if ob.get("asks") else 0
        if bid <= 0 or ask <= 0:
            return 1.0
        mid = (bid + ask) / 2
        return abs(ask - bid) / mid

    def _log_rebalance_event(self, event: dict[str, Any]) -> None:
        p = self.config.rebalance_log_path
        p.parent.mkdir(parents=True, exist_ok=True)
        exists = p.exists()
        with p.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["ts", "symbol", "target_delta", "actual_delta", "drift", "action", "qty", "spread", "dry_run"],
            )
            if not exists:
                w.writeheader()
            w.writerow(event)

    def check_position_drift(self, symbol: str, target_delta: float, drift_deadzone: float) -> dict[str, float | bool | str]:
        spot_qty, perp_qty = self._fetch_spot_and_perp_qty(symbol)
        total_equity = self.fetch_total_equity()

        actual_delta, drift, status_override = self.calculate_drift(spot_qty, perp_qty, target_delta, total_equity)
        if status_override == "FLAT_LEGAL":
            return {
                "checked": True,
                "symbol": symbol,
                "rebalanced": False,
                "actual_delta": actual_delta,
                "drift": drift,
                "status": "FLAT_LEGAL",
                "reason": "total_equity_below_10",
            }
        if status_override == "NO_SPOT_LEG":
            return {
                "checked": True,
                "symbol": symbol,
                "rebalanced": False,
                "actual_delta": actual_delta,
                "drift": drift,
                "status": "NO_SPOT_LEG",
                "reason": "no_spot",
            }

        spread = self._fetch_spread(symbol)

        if drift <= drift_deadzone:
            return {"checked": True, "symbol": symbol, "rebalanced": False, "actual_delta": actual_delta, "drift": drift}
        if spread > self.config.max_spread_for_rebalance:
            return {"checked": True, "symbol": symbol, "rebalanced": False, "actual_delta": actual_delta, "drift": drift, "reason": "spread_too_wide"}

        diff_qty = abs(spot_qty * (actual_delta - target_delta))
        side = "sell" if actual_delta > target_delta else "buy"

        if self.config.dry_run:
            event = {
                "ts": int(time.time()),
                "symbol": symbol,
                "target_delta": round(target_delta, 6),
                "actual_delta": round(actual_delta, 6),
                "drift": round(drift, 6),
                "action": side,
                "qty": round(diff_qty, 8),
                "spread": round(spread, 6),
                "dry_run": True,
                "status": "REBALANCE_SUCCESSFUL",
            }
            self._log_rebalance_event(event)
            return {"checked": True, "rebalanced": True, **event}

        # Hard-state verification (zero-trust): submit, then verify on position state.
        self._ensure_exchange()
        before_perp = perp_qty
        order = self.exchange.create_order(symbol=symbol, type="market", side=side, amount=diff_qty, params={"reduceOnly": False})

        verified = False
        new_perp = before_perp
        start = time.time()
        while time.time() - start < 5.0:
            time.sleep(0.5)
            _, probe_perp = self._fetch_spot_and_perp_qty(symbol)
            if abs(probe_perp - before_perp) > 1e-12:
                verified = True
                new_perp = probe_perp
                break

        if not verified:
            fail_event = {
                "ts": int(time.time()),
                "symbol": symbol,
                "target_delta": round(target_delta, 6),
                "actual_delta": round(actual_delta, 6),
                "drift": round(drift, 6),
                "action": side,
                "qty": round(diff_qty, 8),
                "spread": round(spread, 6),
                "dry_run": False,
                "status": "REBALANCE_FAILED",
                "order_id": str(order.get("id")),
                "reason": "position_not_changed_within_5s",
            }
            self._log_rebalance_event(fail_event)
            return {"checked": True, "rebalanced": False, **fail_event}

        new_actual = (spot_qty - new_perp) / spot_qty if spot_qty > 0 else 0.0
        new_drift = abs(new_actual - target_delta)
        ok_event = {
            "ts": int(time.time()),
            "symbol": symbol,
            "target_delta": round(target_delta, 6),
            "actual_delta": round(new_actual, 6),
            "drift": round(new_drift, 6),
            "action": side,
            "qty": round(diff_qty, 8),
            "spread": round(spread, 6),
            "dry_run": False,
            "status": "REBALANCE_SUCCESSFUL",
            "order_id": str(order.get("id")),
        }
        self._log_rebalance_event(ok_event)
        return {"checked": True, "rebalanced": True, **ok_event}

    def persist_state(self, payload: dict[str, Any]) -> None:
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.state_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def run(self) -> None:
        self.startup_self_check()
        self.start_equity = self.fetch_total_equity()
        LOG.info("guardian started | start_equity=%.4f", self.start_equity)

        while self.active:
            try:
                current = self.fetch_total_equity()
                dd = self.compute_drawdown(current)

                runtime = self._read_runtime_state()
                registry = self._read_registry()
                hybrid_map = runtime.get("hybrid") if isinstance(runtime.get("hybrid"), dict) else {}

                drift_checks = {}
                for symbol, cfg in registry.items():
                    if not bool(cfg.get("enabled", True)):
                        continue
                    target_delta = float((hybrid_map.get(symbol) or {}).get("target_delta", 0.0))
                    drift_deadzone = float(cfg.get("drift_threshold", self.config.drift_deadzone))
                    drift_checks[symbol] = self.check_position_drift(symbol, target_delta, drift_deadzone)
                    LOG.info("DRIFT_CALC symbol=%s target_delta=%.4f result=%s", symbol, target_delta, drift_checks[symbol])

                    # Alert when drift > 5% for 3 consecutive cycles
                    d = float((drift_checks[symbol] or {}).get("drift") or 0.0)
                    if d > 0.05:
                        self.high_drift_cycles[symbol] = self.high_drift_cycles.get(symbol, 0) + 1
                    else:
                        self.high_drift_cycles[symbol] = 0

                    if self.high_drift_cycles.get(symbol, 0) >= 3:
                        send_telegram_alert(
                            f"⚠️ High Drift detected on {symbol}: {d:.2%}. Attempting Persistent Close / Rebalance."
                        )
                        self.high_drift_cycles[symbol] = 0

                    time.sleep(0.5)

                state = {
                    "ts": int(time.time()),
                    "start_equity": self.start_equity,
                    "current_equity": current,
                    "drawdown": dd,
                    "lock_threshold": self.config.daily_equity_lock_pct,
                    "dry_run": self.config.dry_run,
                    "status": "monitoring",
                    "drift_checks": drift_checks,
                }
                self.persist_state(state)

                if dd >= 0.10:
                    send_telegram_alert("🚨 Stop Loss Hit (>10% drawdown). Closing all positions and shutting down.")
                    self.emergency_flatten("drawdown >= 10% emergency shutdown")
                    break

                if dd >= self.config.daily_equity_lock_pct:
                    send_telegram_alert(
                        f"⚠️ Daily equity lock triggered: drawdown {dd:.2%} >= {self.config.daily_equity_lock_pct:.2%}."
                    )
                    self.emergency_flatten(f"drawdown {dd:.4f} >= threshold {self.config.daily_equity_lock_pct:.4f}")
                    break

                time.sleep(self.config.loop_seconds)
            except Exception as exc:  # noqa: BLE001
                LOG.exception("CRITICAL_ERROR guardian loop: %s", exc)
                autonomous = os.getenv("AUTONOMOUS_SOAK", "false").lower() in {"1", "true", "yes"}
                if autonomous:
                    LOG.error("AUTONOMOUS_SOAK: stopping guardian after CRITICAL_ERROR")
                    break
                time.sleep(max(1.0, self.config.loop_seconds))


def load_config(base_dir: Path) -> GuardianConfig:
    live_cfg_path = base_dir / "config" / "live_config.json"
    if not live_cfg_path.exists():
        live_cfg_path = base_dir / "config" / "live_config.example.json"

    live = json.loads(live_cfg_path.read_text(encoding="utf-8"))
    risk_path = base_dir / live.get("paths", {}).get("risk_limits", "config/risk_limits.json")
    risk = json.loads(risk_path.read_text(encoding="utf-8"))

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
        drift_deadzone=float(live.get("runtime", {}).get("drift_deadzone", 0.01)),
        max_spread_for_rebalance=float(live.get("runtime", {}).get("max_spread_for_rebalance", 0.001)),
        runtime_state_path=base_dir / live.get("paths", {}).get("runtime_state", "logs/runtime_state.json"),
        rebalance_log_path=base_dir / live.get("paths", {}).get("rebalance_log", "logs/rebalance_events.csv"),
        pairs_registry_path=base_dir / live.get("paths", {}).get("pairs_registry", "config/pairs_registry.json"),
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    log_path = root / "logs" / "guardian.log"
    audit_log = Path(os.getenv("OVERNIGHT_AUDIT_LOG", str(root / "logs" / "overnight_audit.log")))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    audit_log.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    ah = logging.FileHandler(audit_log, encoding="utf-8")
    ah.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(ah)
    logger.addHandler(sh)

    Guardian(load_config(root)).run()
