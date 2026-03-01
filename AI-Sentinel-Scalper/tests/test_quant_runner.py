import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.quant_runner import run_vectorized_backtest


class QuantRunnerTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("pandas") is None, "pandas not installed")
    def test_vectorized_backtest_returns_report(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.csv"
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["close"])
                for v in [100, 101, 100.5, 102, 101.8, 103, 104, 103.5, 105, 106]:
                    w.writerow([v])

            report = run_vectorized_backtest(p)
            self.assertIsNotNone(report.metrics.sharpe_ratio)
            self.assertIn(report.verdict, {"validated_for_demo", "hold"})
            self.assertGreaterEqual(report.metrics.win_rate, 0)
            self.assertLessEqual(report.metrics.win_rate, 1)
            self.assertGreaterEqual(report.metrics.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
