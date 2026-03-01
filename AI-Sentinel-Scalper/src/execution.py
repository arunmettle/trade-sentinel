from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass
class PersistentCloseResult:
    ok: bool
    filled_qty: float
    remaining_qty: float
    attempts: int
    last_order_id: str | None
    reason: str


def persistent_limit_close(
    exchange,
    symbol: str,
    side: str,
    qty: float,
    *,
    category_symbol: str = "BTCUSDT",
    position_idx: int = 0,
    check_every_seconds: float = 1.0,
    max_attempts: int = 12,
    walk_step_pct: float = 0.001,
) -> PersistentCloseResult:
    """Persistent reduce-only limit close with cancel/replace walk.

    - Places PostOnly limit order.
    - Waits 5s-ish (via polling), then cancel+replace closer to market.
    - Verifies by position size delta from exchange truth.
    """
    if qty <= 0:
        return PersistentCloseResult(True, 0.0, 0.0, 0, None, "nothing_to_close")

    info = exchange.publicGetV5MarketInstrumentsInfo({"category": "linear", "symbol": category_symbol})
    item = ((info.get("result") or {}).get("list") or [{}])[0]
    lot = item.get("lotSizeFilter") or {}
    pf = item.get("priceFilter") or {}
    step = float(lot.get("qtyStep") or 0.001)
    tick = float(pf.get("tickSize") or 0.1)

    remaining = max(step, math.floor(qty / step) * step)
    last_order_id = None

    def get_pos_size() -> float:
        raw = exchange.privateGetV5PositionList({"category": "linear", "symbol": category_symbol})
        p = ((raw.get("result") or {}).get("list") or [{}])[0]
        return abs(float(p.get("size") or 0.0))

    before = get_pos_size()

    for attempt in range(1, max_attempts + 1):
        ob = exchange.fetch_order_book(symbol, limit=20)
        best_bid = float(ob["bids"][0][0]) if ob.get("bids") else 0
        best_ask = float(ob["asks"][0][0]) if ob.get("asks") else 0
        if best_bid <= 0 or best_ask <= 0:
            return PersistentCloseResult(False, before - remaining, remaining, attempt, last_order_id, "orderbook_unavailable")

        if side.lower() == "buy":
            px = best_ask * (1 + walk_step_pct * (attempt - 1))
        else:
            px = best_bid * (1 - walk_step_pct * (attempt - 1))
        px = max(tick, math.floor(px / tick) * tick)

        resp = exchange.privatePostV5OrderCreate(
            {
                "category": "linear",
                "symbol": category_symbol,
                "side": side.capitalize(),
                "orderType": "Limit",
                "qty": str(remaining),
                "price": str(px),
                "timeInForce": "PostOnly",
                "positionIdx": position_idx,
                "reduceOnly": True,
            }
        )
        last_order_id = ((resp.get("result") or {}).get("orderId") or None)

        waited = 0.0
        while waited < 5.0:
            time.sleep(check_every_seconds)
            waited += check_every_seconds
            now = get_pos_size()
            if now < before:
                filled = before - now
                remaining = max(0.0, qty - filled)
                if remaining <= step:
                    return PersistentCloseResult(True, qty, 0.0, attempt, last_order_id, "filled")
                before = now
                break

        # cancel stale order before next walk step
        if last_order_id:
            try:
                exchange.privatePostV5OrderCancel({"category": "linear", "symbol": category_symbol, "orderId": last_order_id})
            except Exception:
                pass

    final_now = get_pos_size()
    filled = max(0.0, qty - final_now)
    return PersistentCloseResult(False, filled, max(0.0, final_now), max_attempts, last_order_id, "max_attempts_exceeded")
