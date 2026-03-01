from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HybridPolicy:
    base_hedge: float = 1.0
    max_tilt: float = 0.4
    panic_score: float = 30.0
    high_funding_override: float = 0.0003  # 0.03%
    sentiment_drop_rehedge_points: float = 20.0


class HybridManager:
    def __init__(self, gate_path: str | Path, policy: HybridPolicy | None = None) -> None:
        self.gate_path = Path(gate_path)
        self.policy = policy or HybridPolicy()

    def _read_gate(self) -> dict:
        if not self.gate_path.exists():
            return {"score": 50, "status": "CAUTIOUS", "allow_trading": True}
        try:
            return json.loads(self.gate_path.read_text(encoding="utf-8"))
        except Exception:
            return {"score": 50, "status": "CAUTIOUS", "allow_trading": True}

    def compute_target_delta(self) -> dict:
        gate = self._read_gate()
        score = float(gate.get("score", 50))
        funding_rate = float(gate.get("funding_rate", 0.0))
        score_drop_1h = float(gate.get("score_drop_1h", 0.0))

        # capital preservation overrides
        if score < self.policy.panic_score or score_drop_1h >= self.policy.sentiment_drop_rehedge_points:
            hedge_ratio = 1.0
            mode = "PANIC_REHEDGE"
        elif funding_rate >= self.policy.high_funding_override:
            hedge_ratio = 1.0
            mode = "MAX_FUNDING"
        elif score > 50:
            tilt = ((score - 50) / 50) * self.policy.max_tilt
            hedge_ratio = max(0.0, min(1.0, self.policy.base_hedge - tilt))
            mode = "BULLISH_TILT"
        else:
            hedge_ratio = 1.0
            mode = "NEUTRAL_HEDGED"

        target_delta = round(1.0 - hedge_ratio, 4)
        return {
            "score": score,
            "funding_rate": funding_rate,
            "score_drop_1h": score_drop_1h,
            "target_delta": target_delta,
            "target_hedge_ratio": round(hedge_ratio, 4),
            "hybrid_mode": mode,
        }
