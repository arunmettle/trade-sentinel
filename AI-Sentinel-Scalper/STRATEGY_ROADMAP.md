# Strategy Roadmap Pivot (Track A / Track B)

## Objective
Prioritize high-Sharpe, risk-controlled strategies and reduce dependence on directional scalp noise.

## Track A — Funding Rate Arbitrage (Primary)

### Thesis
Market-neutral carry capture (spot long + perp short) to harvest funding yield with low directional exposure.

### Backtest requirements
- Historical funding rates by symbol and interval
- Spot/perp basis snapshots
- Trading fees + borrow/funding costs
- Slippage assumptions and rebalance costs

### Metrics
- Net carry yield
- Sharpe ratio
- Max drawdown
- Hedge drift / rebalance frequency
- Liquidation buffer health

### Exit criteria
- Pass if Sharpe >= 2.5 and MDD <= 3% over 90-day simulation.

---

## Track B — AI-Filtered Mean Reversion (Secondary)

### Thesis
Use pre-filter score (micro-trend confidence) to reduce fake RSI/Bollinger signals.

### Baseline entry logic
- `micro_trend_score > 80`
- `RSI < 30`
- first bullish candle close confirmation

### Metrics
- Sharpe ratio
- Max drawdown
- Win rate
- Profit factor
- Regime-specific performance split

### Exit criteria
- Pass if Sharpe >= 2.0 and MDD <= 1.5% on 90-day backtest.

---

## Execution order
1. Build Track B quickly in current engine and backtest 90d.
2. Build Track A simulation module and run 90d carry backtest.
3. Compare A vs B on common report template.
4. Promote one to forward/demo lane.
