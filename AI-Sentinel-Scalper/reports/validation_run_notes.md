# Validation Run Notes

Date: 2026-03-01

## What was executed automatically
- Created synthetic datasets:
  - `data/btcusdt_1m_30d.csv`
  - `data/btcusdt_1m_forward_48h.csv`
- Ran:
  - `scripts/run_backtest.py`
  - `scripts/run_forward.py`
  - `scripts/finalize_readiness.py`

## Output artifacts produced
- `reports/quant_report.json`
- `reports/backtest_summary.md`
- `reports/forward_report.json`
- `reports/forward_quant_report.json`
- `reports/demo_report.json` (template copy; no real demo run yet)
- `reports/launch_readiness_auto.md`

## Important caveat
These results are from **synthetic data** and not from real Bybit historical/demo execution. They are useful to validate pipeline wiring only, not strategy viability.

## Next required real-world steps
1. Replace synthetic CSVs with real 1m Bybit data.
2. Run 48h unseen forward window with real market data.
3. Run 24h Bybit Demo (UTA) and populate `reports/demo_report.json` with actual metrics.
