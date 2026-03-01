import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gate_evaluator import evaluate_backtest, evaluate_promotion


class GateEvaluatorTests(unittest.TestCase):
    def test_backtest_pass(self):
        self.assertEqual(evaluate_backtest(2.1, 0.01), "pass")

    def test_backtest_fail(self):
        self.assertEqual(evaluate_backtest(1.9, 0.01), "fail")
        self.assertEqual(evaluate_backtest(2.1, 0.02), "fail")

    def test_promotion(self):
        self.assertEqual(evaluate_promotion(0.10, 0.095), "promote")
        self.assertEqual(evaluate_promotion(0.10, 0.20), "hold")


if __name__ == "__main__":
    unittest.main()
