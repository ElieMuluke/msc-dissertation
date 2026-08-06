# PRD-B — Production AML Platform Additions

Owner: Elie Muluke. Status: agreed 2026-08-05.
Relationship to PRD-A: the agents deployed here are the **same Python modules** the experiment measures — one code path, two entry points (harness import, FastAPI route). The experiment's winning arm + config becomes the default pipeline after Tuesday's analysis. Build proceeds in parallel with the sweep; every rule in PRD-A "Sweep operations" binds this work too (dev inference on `:11436` only).

## What exists (do not rebuild)

`backend/app/`: FastAPI (`main.py`), RAG over AML corpus (chroma, `ingestion/rag`, `agents/tools.py` → `search_aml_corpus` StructuredTool), tabular ingestion + sqlite (`ingestion/tabular`, `tabular_data_db.sqlite`), routes `api/routes/{rag,tabular}`, SSE (`api/sse.py`), ragas evaluation module, React/Vite frontend (`frontend/`).

RAG corpus already ingested (2026-08-05): FATF Recommendations 2012, FATF Universal Procedures 2023, FATF ICRG Assessment/Follow-Up Procedures 2022, FATF 5th-Round Methodology handout, JMLSG Guidance Part I (June 2023, updated Aug 2025), JMLSG Guidance Part II (June 2023, updated Dec 2025). Added 2026-08-06: OFSI *UK financial sanctions: general guidance* (Jan 2026, 99 sections) — cited by rulebook SAN-1 in place of JMLSG Part III, which is "currently under review" per jmlsg.org.uk with no downloadable edition.

Pending, in scope below: IBM AML Kaggle tabular dataset (structure exists, data not yet ingested); production rulebook (does not exist yet).

## Goal

Analyst enters an account number (+ optional bank/context) → selected pipeline (single or MAS) investigates using real data tools → returns decision, rationale, and a downloadable audit-grade report. UI switch selects pipeline. Every analysis leaves a full audit trail.

## Scope

### 1. Agent modules (shared with PRD-A)

`app/agents/` grows: `single.py` (monolithic arm), `mas.py` (LangGraph pipeline: Orchestrator-Planner → Data → Policy & Risk → Reporting), `contract.py` (`async arun(case, context) -> AgentResult`). Experiment harness imports these; FastAPI wraps them. Tool *sets* are injected: DFAH mocked tools in the harness, production tools here.

### 2. Production tools

- **IBM dataset ingestion** — download IBM AML Kaggle transactions CSV, load into the tabular sqlite via existing `ingestion/tabular` path; record dataset version + download date.
- **Rulebook authoring** — `backend/data/rulebook.md`: distilled decision rules (risk bands, red flags, required actions, escalation thresholds), each rule citing its JMLSG/FATF source section from the ingested corpus. Versioned; used by the Policy & Risk agent in production. The experiment keeps DFAH's shipped rulebook untouched — the two never mix.
- `query_accounts` / `query_transactions` — parameterised reads over the tabular sqlite (IBM AML Kaggle data, backing store only, no labels involved).
- `sanctions_check` — lookup against downloaded OFAC + HM Treasury + UN consolidated lists (CSV/XML, refreshed manually, file date recorded).
- `country_risk` — FATF high-risk jurisdictions list as a lookup table.
- `search_aml_corpus` — existing RAG tool (JMLSG + FATF 40 corpus), reused as rulebook retrieval.

### 3. Pipeline selection

Config value `pipeline: single | mas` (settings + per-request override). `POST /api/analysis` accepts `{account_id, bank?, pipeline?}`. Response: decision, rationale, report id. SSE progress stream reuses `api/sse.py` so the UI shows agent steps live.

### 4. Reports + audit trail

Per analysis, persist: input, pipeline, model + digest, every tool call with arguments and result row references, rule citations from RAG hits, decision, rationale, timestamps. Render to a report file (markdown → PDF) with an appendix listing the full tool-call trace — the artifact an external audit firm reviews. `GET /api/reports/{id}` downloads it. Storage: sqlite table + files under `backend/data/reports/`.

### 5. Session memory

Production chat/session keeps conversation memory (existing RAG chat pattern). The `arun` contract stays stateless — memory lives strictly outside the shared agent modules, in the API session layer, so the measured code path never gains state.

### 6. Frontend (React)

- Pipeline toggle (single / MAS) in the analysis view.
- Case-analysis form: account number + bank → live agent-step stream → decision card → report download link.
- Experiment progress panel (reads `experiments/results/progress.json` via a thin route) — the follow-up progress bar during the weekend sweep.

### 7. Post-analysis wiring (after Tue 11 Aug)

Set default `pipeline` to the experiment winner; record the choice and its Tier-1 numbers in the report footer ("configuration selected by pre-registered evaluation, see dissertation §Results").

## Acceptance

- One command starts backend + frontend; analysis of a real account id completes on both pipeline settings and produces a downloadable report whose trace names every tool call and source row.
- Harness and API demonstrably import the same `app.agents` modules (test asserts module identity).
- Sanctions/FATF list files present with recorded download dates; report cites at least one rulebook passage retrieved via RAG.
- Session memory test: two consecutive API analyses of the same account share session context; two harness runs of the same case share nothing.

## Out of scope

Auth, multi-user, deployment hardening, model fine-tuning, automatic sanctions-list refresh, LLM-judged narrative scoring (ruled out in review), any change to experiment design constants (PRD-A owns those).
