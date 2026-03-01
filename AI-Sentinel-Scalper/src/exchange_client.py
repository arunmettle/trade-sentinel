from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import ccxt

from src.execution import persistent_limit_close


class ExchangeClient:
    def __init__(self, testnet: bool = True, api_key: str | None = None, api_secret: str | None = None) -> None:
        key = api_key or os.getenv("BYBIT_API_KEY")
        secret = api_secret or os.getenv("BYBIT_API_SECRET")
        if not key or not secret:
            raise RuntimeError("Missing BYBIT_API_KEY/BYBIT_API_SECRET in environment")

        self.spot = ccxt.bybit(
            {
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        self.linear = ccxt.bybit(
            {
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if testnet:
            self.spot.set_sandbox_mode(True)
            self.linear.set_sandbox_mode(True)

    def close_all_positions(self, symbol: str = "BTCUSDT") -> dict:
        """Close both linear hedge leg and spot inventory.

        `symbol` example: BTCUSDT
        """
        out: dict = {"symbol": symbol, "linear_orders": [], "spot_orders": [], "errors": []}

        # 1) Close linear/perp legs with reduceOnly
        perp_symbol = f"{symbol[:-4]}/USDT:USDT" if symbol.endswith("USDT") else "BTC/USDT:USDT"
        try:
            positions = self.linear.fetch_positions([perp_symbol])
            for p in positions or []:
                contracts = float(p.get("contracts") or 0)
                side = str(p.get("side") or "").lower()
                if contracts <= 0:
                    continue
                close_side = "sell" if side == "long" else "buy"

                try:
                    o = self.linear.create_order(
                        symbol=perp_symbol,
                        type="market",
                        side=close_side,
                        amount=contracts,
                        params={"reduceOnly": True, "positionIdx": 0},
                    )
                    out["linear_orders"].append(
                        {"id": o.get("id"), "side": close_side, "qty": contracts, "mode": "market_reduce_only"}
                    )
                except Exception as m_exc:  # noqa: BLE001
                    msg = str(m_exc)
                    if "NoImmediateQtyToFill" not in msg and "EC_NoImmediateQtyToFill" not in msg:
                        raise

                    res = persistent_limit_close(
                        self.linear,
                        symbol=perp_symbol,
                        side=close_side,
                        qty=contracts,
                        category_symbol=symbol,
                        position_idx=0,
                        max_attempts=12,
                        walk_step_pct=0.001,
                    )
                    out["linear_orders"].append(
                        {
                            "id": res.last_order_id,
                            "side": close_side,
                            "qty": contracts,
                            "mode": "persistent_limit_walk_reduce_only",
                            "ok": res.ok,
                            "remaining_qty": res.remaining_qty,
                            "attempts": res.attempts,
                            "reason": res.reason,
                        }
                    )

        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"linear_close_error: {exc}")

        # 2) Close spot inventory (sell base to USDT)
        base = symbol.replace("USDT", "")
        spot_symbol = f"{base}/USDT"
        try:
            bal = self.spot.fetch_balance()
            base_qty = float((bal.get("free") or {}).get(base) or 0)
            if base_qty > 0:
                # round down to base precision
                info = self.spot.publicGetV5MarketInstrumentsInfo({"category": "spot", "symbol": symbol})
                item = ((info.get("result") or {}).get("list") or [{}])[0]
                lot = item.get("lotSizeFilter") or {}
                step = float(lot.get("basePrecision") or lot.get("qtyStep") or 0.000001)
                qty = math.floor(base_qty / step) * step
                if qty > 0:
                    o = self.spot.create_order(symbol=spot_symbol, type="market", side="sell", amount=qty)
                    out["spot_orders"].append({"id": o.get("id"), "side": "sell", "qty": qty})
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"spot_close_error: {exc}")

        out["ok"] = len(out["errors"]) == 0
        return out


def force_sync_state(base_dir: Path, symbol: str = "BTCUSDT", api_key: str | None = None, api_secret: str | None = None) -> dict:
    """Fetch exchange truth and overwrite guardian_state.json snapshot."""
    client = ExchangeClient(testnet=True, api_key=api_key, api_secret=api_secret)
    base = symbol.replace("USDT", "")
    perp_symbol = f"{base}/USDT:USDT"

    bal = client.spot.fetch_balance()
    spot_qty = float((bal.get("total") or {}).get(base) or 0.0)

    pos = client.linear.fetch_positions([perp_symbol])
    perp_qty = abs(float((pos[0].get("contracts") if pos else 0) or 0.0))

    runtime_path = base_dir / "logs" / "runtime_state.json"
    rt = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.exists() else {}
    target = float(((rt.get("hybrid") or {}).get(perp_symbol) or {}).get("target_delta") or 0.0)

    # guard against meaningless ratio when spot leg is near-zero (dust)
    if spot_qty < 1e-4:
        actual = 0.0 if perp_qty == 0 else -1.0
        drift = abs(actual - target)
        reason = "near_zero_spot_leg"
    else:
        actual = (spot_qty - perp_qty) / spot_qty
        drift = abs(actual - target)
        reason = "force_sync"

    state = {
        "ts": int(time.time()),
        "status": "monitoring",
        "dry_run": False,
        "drift_checks": {
            perp_symbol: {
                "checked": True,
                "rebalanced": False,
                "symbol": perp_symbol,
                "actual_delta": actual,
                "target_delta": target,
                "drift": drift,
                "reason": reason,
            }
        },
    }
    p = base_dir / "logs" / "guardian_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"spot_qty": spot_qty, "perp_qty": perp_qty, "target_delta": target, "actual_delta": actual, "drift": drift}
