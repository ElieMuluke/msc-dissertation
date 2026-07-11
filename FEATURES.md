# Feature Requests — Status Tracker

Durable status of every feature request (survives across sessions; the live task list is
the working view, this file is the record). Update on request → in progress → done/blocked.

Status: 🔵 requested · 🟡 in progress · ✅ done · ⛔ blocked

| # | Feature | Status | Notes |
| --- | --- | --- | --- |
| F1 | AML RAG system (ingest + semantic search) | ✅ | LangChain + Chroma. `docs/rag.md` |
| F2 | PDF ingestion (file/dir) | ✅ | `load_pdfs`, per-page metadata |
| F3 | Backend (FastAPI) + frontend (React+Vite+TS) split | ✅ | `backend/`, `frontend/` |
| F4 | Multi-file upload | ✅ | `POST /rag/documents/pdf` accepts many |
| F5 | Clear database button | ✅ | `DELETE /rag/documents` + UI |
| F6 | Evaluation pipeline (retrieval) + MLflow viz | ✅ | `docs/evaluation.md` |
| F7 | List ingested documents | ✅ | `GET /rag/documents` (spec §1) |
| F8 | Delete single document by filename | ✅ | `DELETE /rag/documents/{filename}` (spec §2) |
| F9 | LLM answer-generation over retrieved docs | ✅ | Ollama gemma4:e2b; `POST /rag/answer` |
| F10 | RAG Triad generation evaluation | ✅ | LLM-judge; `triad_run` → MLflow rag-triad |
| F11 | Frontend Tailwind restyle | ✅ | user-implemented |
| F12 | Run frontend (`npm install`) end-to-end | 🔵 | not run yet |
| F13 | Realtime ingestion progress (WebSocket `/ws`) | ✅ | spec §3; per-file frames |
| F14 | Live search monitoring → MLflow | ✅ | experiment rag-search-monitoring |
| F15 | `/health` connectivity (DB + LLM) | ✅ | spec §5; `RagSystem.ping`, `build_llm_ping` |
| F16 | Gemini frontend agent infra (mirror of Claude) | ✅ | `GEMINI.md` + `.gemini/`; Gemini=frontend, Claude=backend |
| F17 | PDF ingestion text-cleanup | ✅ | spec §6; `clean_pdf_text` in `cleaning.py`, applied in `load_pdfs` |
| F18 | Streaming answers (SSE) | ✅ | `POST /rag/answer/stream`; frontend guide in `frontend_spec.md` |
| F19 | RAG retrieval tool for agent | 🟡 | `app/agents/` StructuredTool over RagSystem (JMLSG policy / FATF action) |
| F20 | RAGAS eval (proper lib) → MLflow | 🟡 | replaces scratch triad; `rag-ragas` experiment; Ollama+HF judge |
| F23 | RAGAS audit hardening (golden set, topic adherence, judge, integrity) | 🟡 | `golden_set_v1.jsonl` (57 real-corpus triples), `TopicAdherenceScore` P/R/F1 + `out_of_scope_v1.jsonl`, independent-judge config + self-eval warning, `to_pandas()` + per-query CSV/JSON + NaN handling. Code done + unit-verified; full-scale numeric run pending (CPU-bound) |
| F21 | Stream fix: empty answer (Qwen3 thinking) | ✅ | reasoning routed off `content`; `OLLAMA_REASONING` gate, default off |
| F22 | Collapsible "thinking" channel in SSE | ✅ | `thinking` SSE event; spec §7. Gated by `OLLAMA_REASONING` (model over-thinks on CPU) |
| F24 | Tabular data ingestion (accounts/transactions/patterns) via ORM into SQLite | ✅ | `app/ingestion/tabular/`; SQLAlchemy ORM; `POST /tabular/ingest` + `GET /tabular/counts`; `docs/tabular.md`; `is_laundering` kept but flagged not-a-feature |
| F26 | Tabular ingestion UI (select type, upload, show counts) | ✅ | Implemented by Antigravity/Gemini per `frontend_spec.md` §2 (`frontend/src/components/UploadTabular.tsx`) |
| F27 | Tabular ingestion: pandas CSV loaders, soft relationships, WebSocket progress, clear endpoint | ✅ | `iter_accounts`/`iter_transactions` now via `pandas.read_csv(chunksize=...)`; `models.py` documents from/to bank+account cols as intentional soft (non-FK) relationships; `on_batch` callback → `/ws` progress frames (`uploading`→`inserting`→`completed`/`error`, mirrors PDF ingestion F13); new `DELETE /tabular/data` (`TabularSystem.clear()`); `docs/tabular.md` updated |
| F28 | Tabular ingestion perf fix: SQLite WAL + decoupled commit cadence | ✅ | Root cause: `_insert`/`_insert_ignore_duplicates` committed every 2000-row batch (fsync each time) — real 2.1M-row `HI-Large_accounts.csv` took ~7min. Fix: `store.build_engine` sets `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` per connection; `service.py` commits every 25 batches instead of every batch (`on_batch` progress callback still fires every batch). Measured: same file now ~2min (~3.5x). |
| F29 | Fix 17.1GB upload failure + local-path ingest endpoint | ✅ | Root cause of `{"detail":"There was an error parsing the body"}`: `/tmp` is a 7.6GB tmpfs; both Starlette's multipart spool and our upload tempdir resolve via `tempfile.gettempdir()` → OSError (disk full) on files bigger than that, swallowed by FastAPI into a generic parse-error message. Fix: `app/main.py` redirects `tempfile.tempdir` to `/var/tmp` (disk-backed) at startup unless `TMPDIR` already set; new `POST /tabular/ingest/local` (`{data_type, path}`) ingests a file already on the server's disk with no HTTP upload/temp-copy at all. Verified end-to-end against the real `backend/data/HI-Large_accounts.csv` (2,126,855 rows, ~2m13s). `docs/tabular.md`, `frontend_spec.md` §3 (UI request for Gemini), `backend/README.md` updated. 61/61 tests passing. |
| F30 | Paste/type CSV text ingestion, validated before any DB write | ✅ | New `POST /tabular/ingest/text` (`{data_type, csv_text}`) — `parse_csv_text`/`CsvValidationError` (`loaders.py`) fully parse+validate pasted CSV/TXT text up front; `TabularSystem.ingest_text` only inserts if 100% valid, so a malformed paste leaves the DB untouched and returns `422` with the full list of errors (`{"detail": [...]}`), not just the first. `docs/tabular.md`, `frontend_spec.md` §4 (UI request for Gemini), `backend/README.md` updated. 71/71 tests passing. |

Related: `backend_spec.md` (frontend↔backend API contract), in-session task list (TaskList).
