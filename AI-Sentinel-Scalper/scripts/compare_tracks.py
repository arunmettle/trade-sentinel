#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def load(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    a = load(base / "reports" / "track_a_backtest.json")
    b = load(base / "reports" / "quant_report_90d_track_b_ai.json")

    lines = ["# Track A vs Track B Comparison", ""]
    lines += ["## Track A (Funding Arb)"]
    lines += [f"- Sharpe: {a.get('sharpe_ratio', 'n/a')}", f"- MDD: {a.get('max_drawdown_pct', 'n/a')}", f"- Gate: {a.get('gate', 'n/a')}"]
    lines += ["", "## Track B (AI Mean Reversion)"]
    bm = b.get("metrics", {})
    lines += [f"- Sharpe: {bm.get('sharpe_ratio', 'n/a')}", f"- MDD: {bm.get('max_drawdown_pct', 'n/a')}", f"- Gate: {'pass' if (bm.get('sharpe_ratio', -1) > 2 and bm.get('max_drawdown_pct', 1) < 0.015) else 'fail'}"]

    out = base / "reports" / "track_comparison.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
