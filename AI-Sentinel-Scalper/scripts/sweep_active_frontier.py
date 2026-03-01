#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

import numpy as np

from src.hybrid_manager import HybridManager


def run_sim(registry, steps=900, seed=71):
    random.seed(seed)
    np.random.seed(seed)

    symbols = [s for s, cfg in registry.items() if cfg.get("enabled", True)]
    prices = {"BTC/USDT:USDT": 65000.0, "SOL/USDT:USDT": 130.0, "LINK/USDT:USDT": 19.0}
    scores = {s: 55.0 for s in symbols}

    base = Path(__file__).resolve().parents[1]
    gate_path = base / "config" / "sentiment_gate.json"
    reg_path = base / "config" / "pairs_registry.json"
    reg_path.write_text(json.dumps(registry), encoding="utf-8")

    initial = 10000.0
    cash = initial
    pos = {s: 0.0 for s in symbols}
    fee = 0.0006
    slippage = 0.0002

    trades = 0
    total_fees = 0.0
    gross_alpha = 0.0
    equity = []

    for _ in range(steps):
        for s in symbols:
            vol = {"BTC/USDT:USDT": 0.0018, "SOL/USDT:USDT": 0.0058, "LINK/USDT:USDT": 0.0038}[s]
            r = np.random.normal(0, vol)
            if random.random() < 0.006:
                r += np.random.normal(0, vol * 4)
            prices[s] = max(0.1, prices[s] * (1 + r))

        for s in symbols:
            scores[s] = max(0, min(100, 0.88 * scores[s] + 0.12 * (55 + np.random.normal(0, 5))))

        gate = {"score": float(np.mean(list(scores.values()))), "scores": scores, "allow_trading": True}
        gate_path.write_text(json.dumps(gate), encoding="utf-8")

        targets = HybridManager(gate_path, reg_path).compute_targets()
        capital = cash + sum(pos[s] * prices[s] for s in symbols)

        for s in symbols:
            annual = {"BTC/USDT:USDT": 0.18, "SOL/USDT:USDT": 0.24, "LINK/USDT:USDT": 0.16}[s]
            cash += capital * registry[s].get("weight", 1 / len(symbols)) * (1 - float(targets[s]["target_delta"])) * (
                annual / (365 * 24 * 12)
            )

            w = float(registry[s].get("weight", 1 / len(symbols)))
            tgt_notional = capital * w * float(targets[s]["target_delta"])
            tgt_qty = tgt_notional / prices[s]
            diff = tgt_qty - pos[s]
            notional = abs(diff) * prices[s]
            if notional < float(registry[s].get("min_trade_usd", 100)):
                continue

            score = float(scores[s])
            expected = max(0.0, (score - 50) / 50) * 0.01
            hurdle = (fee + slippage) * float(registry[s].get("hurdle_multiplier", 2.0))
            if expected <= hurdle:
                continue

            fees = notional * (fee + slippage)
            alpha = notional * expected * 0.22

            cash += -diff * prices[s] - fees + alpha
            pos[s] = tgt_qty
            trades += 1
            total_fees += fees
            gross_alpha += alpha

        equity.append(cash + sum(pos[s] * prices[s] for s in symbols))

    arr = np.array(equity)
    rets = np.diff(arr) / arr[:-1]
    mu = float(rets.mean()) if len(rets) else 0.0
    sd = float(rets.std()) if len(rets) else 0.0
    sharpe = (mu / sd * math.sqrt(12 * 24 * 365)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(arr)
    mdd = float(abs(((arr - peak) / peak).min()))

    return {
        "profit_pct": float((arr[-1] - initial) / initial),
        "approx_sharpe": float(sharpe),
        "max_drawdown_pct": mdd,
        "trade_count": trades,
        "total_fees_paid": total_fees,
        "gross_alpha_capture": gross_alpha,
        "net_alpha_minus_fees": gross_alpha - total_fees,
    }


def main():
    base = Path(__file__).resolve().parents[1]
    base_registry = json.loads((base / "config" / "pairs_registry.json").read_text(encoding="utf-8"))

    hurdles = [1.5, 2.0, 2.5, 3.0]
    mins = [300, 400, 500]
    buffs = [8, 10, 12, 15]

    rows = []
    for h, m, b in itertools.product(hurdles, mins, buffs):
        reg = json.loads(json.dumps(base_registry))
        for s in reg:
            if not reg[s].get("enabled", True):
                continue
            reg[s]["hurdle_multiplier"] = h
            reg[s]["min_trade_usd"] = m
            reg[s]["hysteresis_buffer"] = b

        met = run_sim(reg)
        row = {"hurdle_multiplier": h, "min_trade_usd": m, "hysteresis_buffer": b, **met}
        if 20 <= row["trade_count"] <= 120 and row["max_drawdown_pct"] < 0.02:
            rows.append(row)

    rows.sort(key=lambda r: (r["profit_pct"], r["net_alpha_minus_fees"], r["approx_sharpe"]), reverse=True)
    out = {"tested_active": len(rows), "top5": rows[:5]}
    (base / "reports" / "active_frontier_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = ["# Active Frontier Sweep", f"Candidates after constraints: {len(rows)}", "", "## Top 5"]
    for i, r in enumerate(rows[:5], 1):
        lines.append(
            f"{i}. h={r['hurdle_multiplier']}, min={r['min_trade_usd']}, buf={r['hysteresis_buffer']} | "
            f"profit={r['profit_pct']:.4%}, sharpe={r['approx_sharpe']:.3f}, mdd={r['max_drawdown_pct']:.4%}, "
            f"trades={r['trade_count']}, net_alpha_minus_fees={r['net_alpha_minus_fees']:.4f}"
        )
    (base / "reports" / "active_frontier_sweep.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
