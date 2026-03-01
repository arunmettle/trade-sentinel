import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sentiment_agent import compute_market_pulse, update_gate_from_headlines


class SentimentAgentTests(unittest.TestCase):
    def test_compute_market_pulse_shape(self):
        out = compute_market_pulse(["ETF inflow rises", "Exchange hack triggers panic"])
        self.assertIn("score", out)
        self.assertIn("status", out)
        self.assertIn("allow_trading", out)

    def test_gate_write(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sentiment_gate.json"
            out = update_gate_from_headlines(["massive crash panic"], p)
            self.assertTrue(p.exists())
            self.assertIn(out["status"], {"FLAT", "CAUTIOUS", "AGGRESSIVE"})
            self.assertIsInstance(out["allow_trading"], bool)


if __name__ == "__main__":
    unittest.main()
