from __future__ import annotations

import json
from pathlib import Path


def classify_regime_from_prices(closes, short: int = 3, long: int = 20) -> dict:
    if len(closes) < long + 1:
        return {"regime": "HUNT", "adr_ratio": 1.0, "reason": "insufficient_data"}

    ranges = []
    for i in range(1, len(closes)):
        ranges.append(abs(closes[i] - closes[i - 1]))

    adr_short = sum(ranges[-short:]) / short
    adr_long = sum(ranges[-long:]) / long if long > 0 else adr_short
    ratio = adr_short / (adr_long if adr_long != 0 else 1e-9)

    if ratio < 0.9:
        regime = "CRUISE"
    elif ratio > 1.2:
        regime = "STORM"
    else:
        regime = "HUNT"

    return {"regime": regime, "adr_ratio": ratio}


def propose_registry_overrides(regime: str) -> dict:
    if regime == "CRUISE":
        return {"hurdle_multiplier": 3.0, "min_trade_usd": 500}
    if regime == "STORM":
        return {"hurdle_multiplier": 1.2, "min_trade_usd": 100, "hysteresis_buffer": 20}
    return {"hurdle_multiplier": 2.0, "min_trade_usd": 300}


def advisory_snapshot(base_dir: Path, price_history_path: Path | None = None) -> dict:
    # read simple price history if present; else fallback from sentiment current prices
    closes = []
    if price_history_path and price_history_path.exists():
        try:
            closes = json.loads(price_history_path.read_text(encoding="utf-8")).get("closes", [])
        except Exception:
            closes = []

    if not closes:
        sent_path = base_dir / "config" / "sentiment_gate.json"
        try:
            sent = json.loads(sent_path.read_text(encoding="utf-8"))
            prices = sent.get("prices") or {}
            closes = [float(v) for v in prices.values() if isinstance(v, (int, float))]
        except Exception:
            closes = [1.0, 1.0, 1.0, 1.0]

    info = classify_regime_from_prices(closes)
    return {
        "active_regime": info["regime"],
        "adr_ratio": info["adr_ratio"],
        "proposed_overrides": propose_registry_overrides(info["regime"]),
        "advisory_only": True,
    }
