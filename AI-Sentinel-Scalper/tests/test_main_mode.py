import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.main import resolve_trade_mode


class MainModeTests(unittest.TestCase):
    def test_regime_c_forces_flat(self):
        strategy = {"regime": "C", "status": "active"}
        sentiment = {"allow_trading": True}
        mode = resolve_trade_mode(strategy, sentiment)
        self.assertEqual(mode["mode"], "FLAT")
        self.assertFalse(mode["allow_new_trades"])

    def test_sentiment_block_forces_flat(self):
        strategy = {"regime": "A", "status": "active"}
        sentiment = {"allow_trading": False}
        mode = resolve_trade_mode(strategy, sentiment)
        self.assertEqual(mode["mode"], "FLAT")

    def test_active_when_strategy_and_sentiment_allow(self):
        strategy = {"regime": "A", "status": "active"}
        sentiment = {"allow_trading": True}
        mode = resolve_trade_mode(strategy, sentiment)
        self.assertEqual(mode["mode"], "ACTIVE")
        self.assertTrue(mode["allow_new_trades"])


if __name__ == "__main__":
    unittest.main()
