from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def append_journal_entry(
    memory_path: str | Path,
    win_rate: float,
    pnl: float,
    avg_slippage: float,
    key_learning: str,
    architect_instruction: str,
    technical_debt: str = "",
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    block = (
        f"\n## Session Review: {ts}\n"
        f"- Performance: win_rate={win_rate:.2%} | pnl={pnl:.4f} | avg_slippage={avg_slippage:.5f}\n"
        f"- Key Learning: {key_learning}\n"
        f"- Instruction for Architect: {architect_instruction}\n"
        f"- Technical Debt: {technical_debt or 'n/a'}\n"
    )
    path = Path(memory_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(block)
