#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

import numpy as np

from src.hybrid_manager import HybridManager


def run_sim(registry, steps=800, seed=11):
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
    equity = []

    for _ in range(steps):
        for s in symbols:
            vol = {"BTC/USDT:USDT": 0.0018, "SOL/USDT:USDT": 0.0055, "LINK/USDT:USDT": 0.0038}[s]
            r = np.random.normal(0, vol)
            if random.random() < 0.005:
                r += np.random.normal(0, vol * 5)
            prices[s] = max(0.1, prices[s] * (1 + r))

        for s in symbols:
            scores[s] = max(0, min(100, 0.9 * scores[s] + 0.1 * (55 + np.random.normal(0, 4))))

        gate = {"score": float(np.mean(list(scores.values()))), "scores": scores, "allow_trading": True}
        gate_path.write_text(json.dumps(gate), encoding="utf-8")

        targets = HybridManager(gate_path, reg_path).compute_targets()

        capital = cash + sum(pos[s] * prices[s] for s in symbols)
        for s in symbols:
            w = float(registry[s].get("weight", 1 / len(symbols)))
            target_notional = capital * w * float(targets[s]["target_delta"])
            target_qty = target_notional / prices[s]
            diff = target_qty - pos[s]
            if abs(diff * prices[s]) < float(registry[s].get("min_trade_usd", 100)):
                continue
            trade_notional = abs(diff) * prices[s]
            trade_fee = trade_notional * fee
            cash += -diff * prices[s] - trade_fee
            pos[s] = target_qty

        equity.append(cash + sum(pos[s] * prices[s] for s in symbols))

    arr = np.array(equity)
    rets = np.diff(arr) / arr[:-1]
    mu = float(rets.mean()) if len(rets) else 0.0
    sig = float(rets.std()) if len(rets) else 0.0
    sharpe = (mu / sig * math.sqrt(12 * 24 * 365)) if sig > 0 else 0.0
    peak = np.maximum.accumulate(arr)
    mdd = float(abs(((arr - peak) / peak).min()))
    profit = float((arr[-1] - initial) / initial)

    return {"profit_pct": profit, "sharpe": float(sharpe), "mdd": mdd}


def main():
    base = Path(__file__).resolve().parents[1]
    base_registry = json.loads((base / "config" / "pairs_registry.json").read_text(encoding="utf-8"))

    btc_tilts = [0.2, 0.3, 0.4]
    sol_tilts = [0.3, 0.5, 0.6]
    link_tilts = [0.2, 0.3, 0.4]
    buffers = [4, 5, 8]

    rows = []
    for bt, st, lt, buf in itertools.product(btc_tilts, sol_tilts, link_tilts, buffers):
        reg = json.loads(json.dumps(base_registry))
        reg["BTC/USDT:USDT"]["max_tilt"] = bt
        reg["SOL/USDT:USDT"]["max_tilt"] = st
        reg["LINK/USDT:USDT"]["max_tilt"] = lt
        for s in reg:
            reg[s]["hysteresis_buffer"] = buf

        met = run_sim(reg, steps=700, seed=17)
        rows.append({"btc_tilt": bt, "sol_tilt": st, "link_tilt": lt, "buffer": buf, **met})

    rows.sort(key=lambda x: (x["sharpe"], x["profit_pct"]), reverse=True)
    top = rows[:10]
    out = {"tested": len(rows), "top10": top}
    (base / "reports" / "hybrid_sweep_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = ["# Hybrid Parameter Sweep (Dry-Run)", f"Tested combos: {len(rows)}", "", "## Top 10"]
    for i, r in enumerate(top, 1):
        md.append(
            f"{i}. btc_tilt={r['btc_tilt']}, sol_tilt={r['sol_tilt']}, link_tilt={r['link_tilt']}, buffer={r['buffer']} | "
            f"profit={r['profit_pct']:.4%}, sharpe={r['sharpe']:.3f}, mdd={r['mdd']:.4%}"
        )
    (base / "reports" / "hybrid_sweep_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(top[0], indent=2))


if __name__ == "__main__":
    main()
