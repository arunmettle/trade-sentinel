# M6 Validation Checklist

## A) Backtest Gate (Required)

- [ ] Use 30 days of 1m data for target symbol(s)
- [ ] Include trading fees and slippage in simulation
- [ ] Report metrics:
  - [ ] Sharpe Ratio
  - [ ] Max Drawdown (MDD)
  - [ ] Profit Factor
  - [ ] Win Rate
- [ ] Gate criteria met:
  - [ ] Sharpe > 2.0
  - [ ] MDD < 1.5%

Artifacts:
- `reports/quant_report.json`
- `reports/backtest_summary.md`

## B) Forward Gate (Required)

- [ ] Run forward test on unseen most-recent 48h data
- [ ] Record PnL and trade count
- [ ] Confirm positive net PnL

Artifacts:
- `reports/forward_report.json`

## C) Demo Gate (Required)

- [ ] Run 24h on Bybit Demo (UTA)
- [ ] Verify guardian state logs during run
- [ ] Verify orchestrator and sentiment gate updates during run
- [ ] Compare demo PnL vs backtest expected PnL
- [ ] Promotion threshold met (within 15% drift)

Artifacts:
- `reports/demo_report.json`
- `logs/guardian_state.json` snapshot
- `logs/runtime_state.json` snapshot

## D) Safety and Ops Checks (Required)

- [ ] Dry-run kill-switch tested and logged
- [ ] Live kill-switch path validated in safe demo scenario
- [ ] API keys not hardcoded in repo
- [ ] Runbook reviewed and usable
- [ ] Dashboard shows health state correctly

## E) Go / No-Go Decision

- [ ] Generate final readiness report (`reports/launch_readiness.md`)
- [ ] Manual human approval before any live promotion
