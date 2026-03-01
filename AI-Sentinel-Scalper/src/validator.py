from __future__ import annotations

import logging
import os

LOG = logging.getLogger("validator")


def validate_bybit_netting_mode(exchange, symbol: str) -> bool:
    """Best-effort preflight for Bybit position mode.

    Expectation for Hybrid logic: One-Way / Netting mode (positionIdx == 0).
    """
    try:
        market = symbol.replace("/", "").replace(":", "")
        # Bybit v5 endpoint via ccxt raw method
        res = exchange.privateGetV5PositionList({"category": "linear", "symbol": market})
        rows = ((res or {}).get("result") or {}).get("list") or []
        if not rows:
            LOG.warning("Preflight: no position rows returned for %s; cannot verify mode.", symbol)
            return False

        # positionIdx: 0 one-way, 1/2 hedge legs
        idx = int(rows[0].get("positionIdx", 0))
        if idx != 0:
            LOG.error("CRITICAL: %s appears to be in Hedge mode (positionIdx=%s).", symbol, idx)
            return False

        LOG.info("Preflight OK: %s appears to be in Netting/One-Way mode.", symbol)
        return True
    except Exception as exc:  # noqa: BLE001
        LOG.error("Preflight check failed for %s: %s", symbol, exc)
        return False


def maybe_validate_startup(exchange, symbol: str, dry_run: bool) -> bool:
    """Run startup preflight checks.

    In dry_run we only warn and continue.
    In live mode, fail-fast if netting mode is not verified.
    """
    ok = validate_bybit_netting_mode(exchange, symbol)
    if not ok and not dry_run:
        return False
    return True
