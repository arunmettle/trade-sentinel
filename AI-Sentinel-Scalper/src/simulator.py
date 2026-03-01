from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("simulator")


@dataclass
class SimTrade:
    timestamp: str
    symbol: str
    side: str
    qty: float
    price: float
    fee: float
    notional: float
    order_type: str
    mode: str = "DRY_RUN"


class DryRunSimulator:
    def __init__(self, base_dir: str | Path, fee_rate: float = 0.0006) -> None:
        self.base_dir = Path(base_dir)
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.trades_path = self.logs_dir / "sim_trades.csv"
        self.portfolio_path = self.logs_dir / "simulated_portfolio.json"
        self.fee_rate = fee_rate

        if self.portfolio_path.exists():
            self.portfolio = json.loads(self.portfolio_path.read_text(encoding="utf-8"))
        else:
            self.portfolio = {"usdt_balance": 10000.0, "positions": {}}
            self._save_portfolio()

    def _save_portfolio(self) -> None:
        self.portfolio_path.write_text(json.dumps(self.portfolio, indent=2), encoding="utf-8")

    def _append_trade(self, t: SimTrade) -> None:
        exists = self.trades_path.exists()
        with self.trades_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(asdict(t).keys()))
            if not exists:
                w.writeheader()
            w.writerow(asdict(t))

    def simulate_order(self, symbol: str, side: str, qty: float, price: float, order_type: str = "limit") -> dict:
        notional = qty * price
        fee = notional * self.fee_rate
        ts = datetime.now(timezone.utc).isoformat()

        # Simple balance effect for shadow accounting
        if side.lower() == "buy":
            self.portfolio["usdt_balance"] -= (notional + fee)
        else:
            self.portfolio["usdt_balance"] += (notional - fee)

        pos = self.portfolio["positions"].get(symbol, 0.0)
        pos += qty if side.lower() == "buy" else -qty
        self.portfolio["positions"][symbol] = pos

        trade = SimTrade(
            timestamp=ts,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            fee=fee,
            notional=notional,
            order_type=order_type,
        )
        self._append_trade(trade)
        self._save_portfolio()

        LOG.info("[SIM] %s %.6f %s @ %.2f fee=%.4f", side.upper(), qty, symbol, price, fee)
        return asdict(trade)
