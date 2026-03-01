from __future__ import annotations

import logging

LOG = logging.getLogger("validators")


def validate_bybit_netting_mode(exchange, symbol: str) -> bool:
    """Validate One-Way (Netting) mode for Bybit linear perps.

    Bybit V5 convention:
    - positionIdx 0 => one-way/netting
    - positionIdx 1/2 => hedge legs
    """
    try:
        market = symbol.split(":")[0].replace("/", "")
        response = exchange.privateGetV5PositionList({"category": "linear", "symbol": market})
        pos_info = ((response or {}).get("result") or {}).get("list") or []
        if not pos_info:
            LOG.info("No existing position for %s. Assuming default mode.", symbol)
            return True

        current_mode = int(pos_info[0].get("positionIdx", 0))
        if current_mode != 0:
            LOG.error("CRITICAL: %s in HEDGE MODE (idx=%s).", symbol, current_mode)
            LOG.error("Hybrid Track C requires ONE-WAY (Netting) mode.")
            return False

        LOG.info("Preflight OK: %s confirmed in Netting mode.", symbol)
        return True
    except Exception as exc:  # noqa: BLE001
        LOG.error("Validator error: %s", exc)
        return False
