from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FundingArbResult:
    net_yield_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    rebalance_count: int


def simulate_funding_arb(
    funding_rates,
    fees_per_rebalance_pct: float = 0.0004,
    rebalance_threshold_pct: float = 0.01,
):
    """Phase-1 funding arb simulator scaffold.

    Inputs expected:
    - funding_rates: iterable of periodic funding rates (decimal, e.g., 0.0001)

    Model:
    - carry accrues from funding rates
    - periodic rebalance penalty approximated by threshold events (placeholder)
    """
    import numpy as np

    fr = np.array(list(funding_rates), dtype=float)
    if fr.size == 0:
        return FundingArbResult(0.0, 0.0, 0.0, 0)

    carry = fr.copy()
    # Placeholder rebalance heuristic from funding volatility
    vol = np.abs(np.diff(fr, prepend=fr[0]))
    rebalance_flags = vol > rebalance_threshold_pct
    rebalance_count = int(rebalance_flags.sum())
    costs = rebalance_flags.astype(float) * fees_per_rebalance_pct

    pnl = carry - costs
    equity = (1 + pnl).cumprod()

    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    mdd = abs(float(dd.min()))

    mu = float(pnl.mean())
    sigma = float(pnl.std()) or 1e-9
    sharpe = (mu / sigma) * (365 ** 0.5)

    return FundingArbResult(
        net_yield_pct=float(equity[-1] - 1),
        sharpe_ratio=float(sharpe),
        max_drawdown_pct=mdd,
        rebalance_count=rebalance_count,
    )
