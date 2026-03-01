# 90-Day Backtest Assessment (Current Baseline)

Date: 2026-03-01
Dataset: `data/btcusdt_1m_90d_real.csv` (Bybit testnet fetch)

## Result
- Gate verdict: **FAIL**

## Why fail
- Max Drawdown is **12.59%** (target is <1.5%).

## Quality caveat
- Net profit and Sharpe are abnormally inflated for a realistic 1m baseline.
- This strongly suggests the current baseline signal + dataset characteristics are not suitable for production decisioning yet.
- Testnet historical candles can include artifacts; production validation should use high-quality mainnet historical data feed.

## Recommendation
1. Keep verdict as **fail**.
2. Replace baseline signal with strategy-specific entry/exit logic from Architect contract.
3. Re-run 90d backtest on cleaned/mainnet-quality data.
4. Add stricter data-quality checks (outlier filtering, continuity checks) before each run.
