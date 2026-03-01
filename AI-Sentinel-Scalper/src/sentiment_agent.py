from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _heuristic_score(headlines: Iterable[str]) -> tuple[int, str]:
    text = " ".join(h.lower() for h in headlines)
    negative = ["hack", "liquidation", "ban", "lawsuit", "exploit", "panic", "crash"]
    positive = ["etf inflow", "adoption", "upgrade", "approval", "partnership", "surge"]
    score = 50
    score -= 8 * sum(word in text for word in negative)
    score += 6 * sum(word in text for word in positive)
    score = max(0, min(100, score))
    if score <= 30:
        status = "FLAT"
    elif score <= 65:
        status = "CAUTIOUS"
    else:
        status = "AGGRESSIVE"
    return score, status


def compute_market_pulse(headlines: list[str] | None = None) -> dict:
    """Compute sentiment gate.

    Phase-1 default uses deterministic heuristic for low cost and offline safety.
    If OPENAI_API_KEY is set and integration enabled later, this can be upgraded.
    """
    headlines = headlines or []
    score, status = _heuristic_score(headlines)
    return {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "status": status,
        "allow_trading": score > 30,
    }


def write_gate(payload: dict, gate_path: str | Path) -> None:
    p = Path(gate_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def update_gate_from_headlines(headlines: list[str], gate_path: str | Path) -> dict:
    payload = compute_market_pulse(headlines)
    write_gate(payload, gate_path)
    return payload


if __name__ == "__main__":
    gate_path = os.getenv("SENTIMENT_GATE_PATH", "config/sentiment_gate.json")
    # phase 1: pass empty headlines if no feed fetch wired yet
    payload = update_gate_from_headlines([], gate_path)
    print(json.dumps(payload))
