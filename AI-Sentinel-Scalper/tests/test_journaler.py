import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.journaler import append_journal_entry


class JournalerTests(unittest.TestCase):
    def test_append_journal_entry(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "memory" / "long_term_memory.md"
            append_journal_entry(
                memory_path=p,
                win_rate=0.6,
                pnl=0.012,
                avg_slippage=0.0004,
                key_learning="Test lesson",
                architect_instruction="Adjust ATR threshold",
                technical_debt="none",
            )
            content = p.read_text(encoding="utf-8")
            self.assertIn("Session Review:", content)
            self.assertIn("Test lesson", content)


if __name__ == "__main__":
    unittest.main()
