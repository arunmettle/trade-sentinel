import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.guardian import Guardian, GuardianConfig


class FakeExchange:
    def __init__(self):
        self.cancelled = False
        self.orders = []

    def fetch_balance(self):
        return {"total": {"USDT": 1000}}

    def cancel_all_orders(self, symbol):
        self.cancelled = True

    def fetch_positions(self, symbols):
        return [
            {"contracts": 2, "side": "long"},
            {"contracts": 0, "side": "short"},
        ]

    def create_order(self, **kwargs):
        self.orders.append(kwargs)


class GuardianTests(unittest.TestCase):
    def _cfg(self, state_path: Path, dry_run=True):
        return GuardianConfig(
            symbol="BTC/USDT:USDT",
            loop_seconds=1,
            dry_run=dry_run,
            daily_equity_lock_pct=0.02,
            state_path=state_path,
            max_retries=2,
            retry_backoff_seconds=0.01,
        )

    def test_compute_drawdown(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._cfg(Path(td) / "state.json")
            g = Guardian(cfg)
            g.start_equity = 1000
            self.assertAlmostEqual(g.compute_drawdown(980), 0.02)
            self.assertAlmostEqual(g.compute_drawdown(1020), 0.0)

    def test_emergency_flatten_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "guardian_state.json"
            g = Guardian(self._cfg(state, dry_run=True))
            g.emergency_flatten("test")
            self.assertFalse(g.active)
            payload = json.loads(state.read_text())
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["event"], "killswitch")

    def test_emergency_flatten_live_uses_exchange(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "guardian_state.json"
            fx = FakeExchange()
            g = Guardian(self._cfg(state, dry_run=False), exchange=fx)
            g.emergency_flatten("live-test")
            self.assertFalse(g.active)
            self.assertTrue(fx.cancelled)
            self.assertEqual(len(fx.orders), 1)
            self.assertEqual(fx.orders[0]["side"], "sell")


if __name__ == "__main__":
    unittest.main()
