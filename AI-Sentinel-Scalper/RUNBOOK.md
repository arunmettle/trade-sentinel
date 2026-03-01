# AI-Sentinel Runbook (M5)

## 1) Setup

```bash
cd AI-Sentinel-Scalper
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ccxt pandas numpy streamlit plotly
```

Create local runtime config:

```bash
cp config/live_config.example.json config/live_config.json
```

Set API keys (only if `dry_run=false`):

```bash
export BYBIT_API_KEY="..."
export BYBIT_API_SECRET="..."
```

## 2) Start components

### Guardian

```bash
python3 src/guardian.py
```

Writes: `logs/guardian_state.json`

### Orchestrator

```bash
python3 src/main.py
```

Writes: `logs/runtime_state.json`, `config/sentiment_gate.json`

### Dashboard

```bash
streamlit run dashboard.py
```

## 3) Health checks

- Guardian loop alive: inspect timestamp updates in `logs/guardian_state.json`
- Orchestrator loop alive: inspect `logs/runtime_state.json`
- Sentiment gate written: inspect `config/sentiment_gate.json`
- Dry run mode: `config/live_config.json -> runtime.dry_run`

## 4) Incident procedures

### A) Kill-switch triggered

Symptoms:
- `logs/guardian_state.json` contains `event: killswitch`

Actions:
1. Stop orchestrator/executor processes.
2. Confirm all orders canceled and positions flat in Bybit UI.
3. Set strategy to Regime C / `status=flat` in `config/live_strategy.json`.
4. Review drawdown cause before restart.

### B) API/auth failure in live mode

Symptoms:
- Guardian startup error for missing key/secret or repeated retry failure.

Actions:
1. Verify env vars present in the same shell.
2. Validate key permissions and testnet/mainnet selection.
3. Switch `dry_run=true` while debugging.

### C) Sentiment gate blocks trading unexpectedly

Actions:
1. Inspect `config/sentiment_gate.json` score/status.
2. Verify sentiment input data and heuristic settings.
3. Keep system in FLAT until validated.

## 5) Safe restart sequence

1. Set `config/live_strategy.json` to `{ "regime": "C", "status": "flat" }`.
2. Start guardian, then orchestrator.
3. Verify healthy state files update.
4. Move strategy to active regime only after checks pass.
