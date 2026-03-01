#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    base = Path(__file__).resolve().parents[1]
    quant = load_json(base / "reports" / "quant_report.json")
    forward = load_json(base / "reports" / "forward_report.json")
    demo = load_json(base / "reports" / "demo_report.json")

    sharpe = ((quant.get("metrics") or {}).get("sharpe_ratio"))
    mdd = ((quant.get("metrics") or {}).get("max_drawdown_pct"))
    backtest_pass = sharpe is not None and mdd is not None and sharpe > 2.0 and mdd < 0.015

    forward_pass = forward.get("verdict") == "pass"

    demo_decision = demo.get("promotion_decision")
    demo_pass = demo_decision == "promote"

    go_live = backtest_pass and forward_pass and demo_pass

    lines = [
        "# Launch Readiness (Auto)",
        f"- Backtest gate: {'PASS' if backtest_pass else 'FAIL/UNKNOWN'}",
        f"- Forward gate: {'PASS' if forward_pass else 'FAIL/UNKNOWN'}",
        f"- Demo gate: {'PASS' if demo_pass else 'FAIL/UNKNOWN'}",
        f"- Final decision: {'GO' if go_live else 'NO-GO'}",
    ]
    out = base / "reports" / "launch_readiness_auto.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"go_live": go_live, "out": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
