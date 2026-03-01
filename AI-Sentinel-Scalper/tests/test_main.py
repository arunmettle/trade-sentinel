import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.main import run_once


class MainOrchestratorTests(unittest.TestCase):
    def test_run_once_generates_runtime_state(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "config").mkdir(parents=True, exist_ok=True)
            (base / "logs").mkdir(parents=True, exist_ok=True)

            (base / "config" / "live_config.json").write_text(
                '{"runtime":{"orchestrator_loop_seconds":60},"paths":{"strategy":"config/live_strategy.json","sentiment_gate":"config/sentiment_gate.json"}}',
                encoding="utf-8",
            )
            (base / "config" / "live_strategy.json").write_text(
                '{"regime":"C","status":"flat"}', encoding="utf-8"
            )

            state = run_once(base, headlines=["etf inflow", "upgrade"])
            self.assertIn("trade_mode", state)
            self.assertFalse(state["trade_mode"]["allow_new_trades"])  # regime C wins
            self.assertTrue((base / "logs" / "runtime_state.json").exists())


if __name__ == "__main__":
    unittest.main()
