# AI-Sentinel Scalper — Task Board

_Last updated: 2026-03-01 (AEST)_

## 0) Project Understanding Snapshot (Token-Efficient Context)

### Objective
Build a production-ready, safety-first Bybit V5 scalping system with:
- **Regime-aware strategy engine** (A trend / B range / C flat-toxic)
- **Hard risk controls** (equity lock, mandatory SL/TP, kill-switch)
- **Validation pipeline** (backtest → forward → demo → live promotion)
- **Operational visibility** (Streamlit dashboard + logs + memory)

### Required Components (from docs in this folder)
1. **Architect Agent** (o3): generate strategy JSON by regime.
2. **Quant Agent** (gpt-4o): vectorized backtesting + validation metrics.
3. **Journaler Agent** (gpt-4o-mini): post-trade critique + long-term memory updates.
4. **Guardian Module** (hard-coded Python): real-time equity protection and emergency flatten.
5. **Sentiment Filter** (gpt-4o-mini + RSS): pause trading during panic/toxic sentiment.
6. **Dashboard** (Streamlit): PnL, open positions, regime/reasoning, sentiment status.
7. **Main Orchestrator**: glues all components with deterministic state + scheduling.

### Success Gates (explicit)
- Backtest: Sharpe > 2.0, MDD < 1.5%, slippage/fees included.
- Forward test: positive PnL on unseen recent 48h.
- Demo: 24h Bybit UTA demo run.
- Promotion: demo PnL within 15% of backtest expectation.

---

## 1) Validation & Requirement Clarification

### Confirmed Requirements
- Regime C = **no trading**.
- Every order must include **SL/TP at creation**.
- Guardian must trigger at **-2% daily equity lock**.
- Prefer maker/post-only behavior to reduce slippage/fees.
- Keep memory loop tight: Architect must read Journaler memory before strategy refresh.

### Risks / Gaps Found (must resolve before coding heavy)
- Target latency statement "<100ms" conflicts with python+network reality in retail setups.
- "Check-loop <100ms" vs sample Guardian loop every 5 seconds conflict.
- Some examples use placeholder credentials and mixed file names (`live_config.json` vs `live_strategy.json`).
- Needs explicit decision on account mode and instrument universe (single symbol vs multi-symbol).

### Working Assumptions (for build start)
- Start with **single symbol** (`BTC/USDT:USDT`) and one account.
- Guardian trigger checks at practical interval (e.g., 1–2s) while keeping exchange rate limits safe.
- Promotion decisions are **manual-confirmed** first, then optional automation.

### Architecture Decisions (Locked for Phase 1)
- Canonical runtime config filename: `config/live_config.json`
- Canonical template filename: `config/live_config.example.json`
- Canonical risk policy file: `config/risk_limits.json`
- Guardian interval policy: default `1s` (`runtime.guardian_loop_seconds`) and configurable
- Promotion policy: `manual_first` until demo validation is stable
- Scope policy: single-symbol execution in phase 1; multi-symbol deferred

---

## 2) Token-Optimization Strategy (Development Process)

To minimize token use during implementation:
- Keep a **single source of truth** in this file + compact `PROJECT_STATE.json` (to be created).
- Use strict templates for logs and agent outputs (fixed schema JSON/Markdown).
- Avoid re-reading long prompts each turn; reference section IDs.
- Store distilled decisions in short bullet changelog after each milestone.
- Prefer deterministic scripts/tests over long conversational debugging.

---

## 3) Milestone Plan & Task Tracking

Status legend: `TODO` | `IN_PROGRESS` | `BLOCKED` | `DONE`

### M0 — Discovery & Architecture Lock
- [x] **DONE** Read all project requirement files.
- [x] **DONE** Extract core components + validation gates.
- [ ] **TODO** Define canonical folder structure and config contracts.
- [ ] **TODO** Resolve requirement ambiguities (latency/check interval/promotion policy).

### M1 — Repo Scaffold & Contracts
- [ ] **TODO** Create folders: `src/`, `config/`, `memory/`, `logs/`, `data/`, `prompts/`, `reports/`.
- [ ] **TODO** Create `config/live_config.example.json` + `config/risk_limits.json`.
- [ ] **TODO** Define typed schemas for:
  - strategy output
  - quant report
  - journal entry
  - sentiment gate
  - guardian state
- [ ] **TODO** Add `.env.example` and secure key loading (no plaintext secrets in code).

### M2 — Safety First (Guardian)
- [x] **DONE** Implement `guardian.py` with:
  - equity baseline capture
  - drawdown monitor
  - emergency cancel/flatten
  - robust error handling + retries
- [x] **DONE** Add dry-run mode and unit tests for kill-switch logic.
- [x] **DONE** Add startup self-check (permissions, API connectivity, account mode).

### M3 — Strategy & Validation Pipeline
- [x] **DONE** Implement Architect I/O contract (`config/live_strategy.json` + schema).
- [x] **DONE** Implement Quant backtest runner (vectorized, fees/slippage, metrics) in `src/quant_runner.py`.
- [x] **DONE** Build gate evaluator (`reports/gate_result.example.json`, `src/gate_evaluator.py`) for promote/hold/reject.
- [x] **DONE** Implement Journaler memory updater (`src/journaler.py` appends to `memory/long_term_memory.md`).

### M4 — Sentiment + Orchestration
- [ ] **TODO** Implement `sentiment_agent.py` with RSS ingest + JSON gate output.
- [ ] **TODO** Implement `main.py` orchestrator with schedule hooks.
- [ ] **TODO** Add passive/flat mode switch integration across components.

### M5 — Dashboard & Operations
- [ ] **TODO** Build `dashboard.py` reading live structured files.
- [ ] **TODO** Add system health panel (guardian alive, last quant run, last journal update).
- [ ] **TODO** Add runbooks (`RUNBOOK.md`) for start/stop/recovery/incidents.

### M6 — Validation & Go/No-Go
- [ ] **TODO** Run backtest and forward-test checklist.
- [ ] **TODO** Run 24h demo soak test.
- [ ] **TODO** Produce launch readiness report + known risks.

---

## 4) Immediate Next Actions (Execution Queue)
1. Freeze canonical project structure and file contracts.
2. Create scaffold + config examples + schema docs.
3. Build Guardian first (safety-critical path).

---

## 5) Compact Change Log
- 2026-03-01: Initial requirement digestion complete; task board created; milestones defined.
