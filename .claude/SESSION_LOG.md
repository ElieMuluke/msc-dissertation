# SESSION LOG — Continuity

Loaded into context every session. Update before wrapping up. Newest entry at top.

Format:
```
## <YYYY-MM-DD HH:MM> — <session focus>
**Done:** <what got finished>
**State:** <current state of the code / repo>
**Next:** <the next step to resume from>
```

---

## 2026-06-17 — Augmented generation via Ollama (F9, task #4)
**Done:** New modular `backend/app/generation/`: config.py (GenerationConfig, default model
gemma4:e2b, env OLLAMA_MODEL/OLLAMA_BASE_URL), prompt.py (pure build_prompt — answer only
from context, cite [id], admit gaps), generator.py (AnswerGenerator depends on search_fn +
complete_fn str->str → decoupled from store+LLM; Answer{answer,citations,used_context};
build_answer_generator wires ChatOllama). Endpoint `POST /rag/answer` (async, asyncio.to_thread
so loop/WS stay free; 503 if Ollama down). Schemas AnswerRequest/CitationOut/AnswerResponse.
deps.get_generator (lru_cache). Added langchain-ollama. Tests: test_generation.py (4, fake LLM)
+ API test_answer (FakeGenerator override). Suite 31 pass. REAL e2e with gemma4:e2b: grounded
cited answer ('...exceeding 10,000 USD... [policy-ctr]'), used_context=True, ~43s CPU latency.
docs/generation.md, backend README, FEATURES F9 ✅. Task #4 done → #3 (RAG Triad) unblocked.
**State:** Full RAG loop done (retrieve→augment→generate). NOTE: user emptied backend/data/
(no aml_sample.json/PDFs) — eval run.py default corpus path now missing; ingest via UI/API or
pass --corpus. Ollama must be running for /rag/answer.
**Next:** F10/#3 RAG Triad eval (groundedness/answer-relevance/context-relevance, LLM judge).
Optional: stream tokens; frontend Ask/Chat view; live generation monitoring.

## 2026-06-17 — Live search monitoring → MLflow (F14)
**Done:** `app/evaluation/monitoring.py`: pure `search_metrics()` + best-effort `log_search()`
(try/except, never breaks search) → experiment `rag-search-monitoring` in same backend/mlflow.db.
Wired into GET /rag/search via FastAPI BackgroundTasks (no added response latency). Metrics:
latency_ms, n_results, top_score, mean_score, k; tags query+doc_type. Tests: test_monitoring.py
(2, pure) + stubbed log_search in API fixture. Suite 26 pass. Real e2e: endpoint search logged
a run (latency 23ms, n_results 3, top_score 0.71). Two MLflow experiments now: rag-retrieval
(offline) + rag-search-monitoring (live). Task #6 done.
**State:** Live monitoring complete. `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
**Next:** F9/#4 LLM generation, F10/#3 RAG Triad. F12 frontend npm.

## 2026-06-17 — Fix WS event-loop blocking
**Done:** WS frames weren't streaming (frontend fell back to HTTP) because sync
`rag.ingest`/`load_pdfs` blocked the async event loop. Fixed: offload both to
`asyncio.to_thread` in ingest_pdfs. Verified under REAL uvicorn (not just TestClient) +
real websockets client: frames arrive spaced over time (uploading→parsing→vectorizing→
completed at 2.66/2.66/2.96/3.2s). 24 tests still pass.
**Gotcha for user:** MLflow only logs when running `python -m app.evaluation.run` — normal
app search does NOT log. And `mlflow ui` MUST use `--backend-store-uri sqlite:///mlflow.db`
(plain `mlflow ui` shows the empty default store). mlflow.db has 4 runs.
**Caveat:** manager is a per-process singleton — WS broadcast only works with a single
uvicorn worker (default). Multi-worker needs a shared pub/sub (Redis). Frontend must
connect to ws://<host>:8000/ws.
**Next:** if frontend still shows HTTP fallback, check its WS URL/connect logic (backend
proven working). Possible future: live retrieval monitoring to MLflow.

## 2026-06-17 — WebSocket ingestion progress (spec §3, F13)
**Done:** `app/realtime.py` — ConnectionManager (connect/disconnect/broadcast, drops dead
conns) + `progress_frame`. `WS /ws` endpoint in main.py (keep-alive). `POST /rag/documents/pdf`
broadcasts per-file frames uploading(10)/parsing(40)/vectorizing(70)/completed(100)/error(0).
Tests: test_realtime.py (3, asyncio.run + FakeWS) + ws integration in test_api (TestClient
websocket_connect). Suite 24 pass. Marked spec §3 ✅, FEATURES F13 ✅, backend README,
task #5 done. No new deps (uvicorn[standard] has websockets).
**State:** All backend_spec items (§1,§2,§3) implemented. Backend feature-complete for
current frontend. Note: ingest is sync in handler (blocks loop during embed) — acceptable
now; offload to threadpool if it becomes an issue.
**Next:** F9/task#4 LLM answer-generation, then F10/task#3 RAG Triad. F12 frontend npm install.

## 2026-06-17 — Document list + delete-by-file endpoints
**Done:** Implemented backend_spec.md §1+§2 (frontend already calls them). Domain-first
(SOLID, no leaked Chroma): `RagSystem.list_sources() -> list[SourceInfo]` and
`delete_by_source(filename) -> int` using store.get(where)/delete(ids). Added SourceInfo
model; stamp `ingested_at` (UTC ISO) into metadata at ingest. Endpoints `GET /rag/documents`
(list) + `DELETE /rag/documents/{filename}` (404 if none) + schemas IngestedDocument/
DeleteResponse. Tests: real facade list/delete in test_rag.py + 3 API tests; suite 20 pass.
Real HTTP e2e OK: upload->list->delete(2 chunks)->empty->404. Marked spec items ✅, updated
backend README. Fixed stale `src.` docstring in rag __init__. Tasks #1,#2 done.
**State:** All frontend-required endpoints now exist. Frontend (Tailwind, user-styled)
should work end-to-end against backend once `npm install` run.
**Next:** Task #4 LLM answer-generation, then #3 RAG Triad eval. Frontend npm install.

## 2026-06-17 — Evaluation pipeline (retrieval + MLflow)
**Done:** New modular `backend/app/evaluation/`: metrics.py (precision@k, recall@k, MRR,
nDCG@k, hit_rate@k — hand-rolled, pure), dataset.py (QueryExample + load_queries JSONL),
runner.py (evaluate(search_fn, queries, k) — decoupled from RAG, fake-testable), run.py
(CLI: ingest sample into throwaway store, evaluate, log to MLflow). Labeled set
datasets/retrieval.jsonl (6 queries vs aml_sample.json). Tests test_evaluation.py (6).
Suite 16 pass. Real run OK: recall/mrr/ndcg/hit_rate=1.0, precision@3=0.333 (1 relevant/query).
Decisions: MLflow local + retrieval-first. Gotchas fixed: MLflow metric keys can't contain
'@' (log as _at_); MLflow 3.x rejects file store -> use sqlite (backend/mlflow.db,
`mlflow ui --backend-store-uri sqlite:///mlflow.db`). Added mlflow to requirements,
gitignore mlflow.db/mlruns/mlartifacts/chroma_eval. docs/evaluation.md.
**State:** Eval pipeline complete + tested + documented. Frontend (user-restyled, Tailwind)
added api calls for GET /rag/documents (list) + DELETE /rag/documents/{filename} —
**backend endpoints NOT yet implemented** (flagged, not built).
**Next:** Implement list/delete-by-file backend endpoints the frontend now expects. Later:
generation metrics (Ragas) once LLM answer step exists.

## 2026-06-17 — Clear-database button
**Done:** Added `RagSystem.clear()` (Chroma `reset_collection`). Backend `DELETE /rag/documents`.
Frontend `api.clearDatabase()` + `ManageDatabase.tsx` (confirm dialog) in App. Test
`test_clear_documents`. Suite 10 pass; verified real clear empties store (1 hit -> 0).
**State:** Clear working end-to-end. Frontend still needs `npm install`.
**Next:** CSV ingestion endpoint + UploadCsv component.

## 2026-06-17 — Multi-file upload
**Done:** Frontend import now multi-file (`<input multiple>`, File[]). Backend
`POST /rag/documents/pdf` accepts `files: list[UploadFile]`, loops + ingests in one request.
`api.ts uploadPdfs(files[])`. Added `tests/test_api.py` (3 tests, FakeRag via
dependency_overrides + monkeypatched load_pdfs — no model/PDF): multi-upload, non-pdf 400,
search. Suite 9 pass. Updated backend/frontend READMEs.
**State:** Multi-upload working + tested. Frontend still needs `npm install` to run.
**Next:** CSV ingestion endpoint + UploadCsv component.

## 2026-06-17 — Split into backend + frontend
**Done:** Restructured to monorepo. `backend/` = FastAPI over RAG code: moved
src/ingestion -> backend/app/ingestion; added app/main.py (FastAPI + CORS), app/deps.py
(shared RagSystem via lru_cache), app/api/routes/rag.py (POST /rag/documents/pdf upload,
GET /rag/search), app/api/schemas.py (Pydantic). `frontend/` = React+Vite+TS (api.ts client,
UploadDocs, SearchDocs, App). Imports src->app; tests moved + updated (6 pass). requirements
+ fastapi/uvicorn/python-multipart/httpx. Added backend/README, frontend/README, root README
rewrite, docs/rag.md path updates, gitignore node_modules/.env. Run backend from backend/.
**State:** Full stack verified via TestClient — health ok, real PDF (Handout 2pp) ingested
through API, search ranked. Frontend scaffolded but `npm install` NOT run yet (no node deps
installed). Real PDFs sit in backend/data/aml_policies + aml_financial_actions.
**Next:** `npm install` + run frontend against backend. Then CSV ingestion endpoint +
UploadCsv component (user's stated next plan). Later: LLM/LangGraph multi-agent layer.

## 2026-06-17 — PDF ingestion + dep cleanup
**Done:** Added `loaders.py` `load_pdfs(path, doc_type, metadata)` (LangChain PyPDFLoader)
— loads a PDF file or directory, one Document per page, with source+page metadata for
traceability, ids `<file>-p<page>`. Wired CLI `ingest-pdf`. Exported `load_pdfs`. Tests:
`tests/test_loaders.py` (monkeypatched PyPDFLoader, 2 tests; suite 6 pass). Cleaned
requirements.txt to direct deps only: dropped chromadb + langchain-core (transitive via
langchain-chroma/-huggingface); kept sentence-transformers (NOT auto-pulled by
langchain-huggingface); added langchain-community + pypdf. Updated docs/rag.md.
**State:** PDF ingestion complete + tested + documented. No real PDF fixture (no reportlab);
adapter tested via monkeypatch, third-party loader trusted.
**Next:** LLM answer-generation or LangGraph multi-agent layer over `as_retriever()`.

## 2026-06-17 — RAG migrated to LangChain
**Done:** Switched AML RAG to industry-standard LangChain (langchain-chroma +
langchain-huggingface + text-splitters). Replaced hand-rolled embeddings/store/ingest/
search modules with thin `rag.py` facade (`RagSystem`, `build_rag`). Kept decoupled domain
types (Document/DocumentType/SearchResult) so callers never import LangChain — store swap
is `build_rag`-only. Added `as_retriever()` (for future LLM/LangGraph agents) and
config-driven chunking (chunk_size/overlap) for long PDFs. Rewrote tests (in-memory Chroma
+ DeterministicFakeEmbedding, 4 pass). Updated requirements, docs/rag.md. E2E CLI verified,
same results as before (CTR policy 0.648).
**State:** Feature complete + documented + tested on LangChain. Same public API.
**Next:** Real PDF/doc loaders (LangChain loaders) + set chunk_size; then LLM generation
or LangGraph multi-agent layer over as_retriever().

## 2026-06-17 — AML RAG feature
**Done:** Built modular AML RAG feature in `src/ingestion/rag/` (config, models,
embeddings, store, ingest, search, `__init__` facade `build_rag`/`RagSystem`, cli).
SOLID/DRY via Embedder + VectorStore Protocols (DI). Removed broken scratch index.py.
Added `data/aml_sample.json`, `tests/test_rag.py` (4 passing, fake backends), `docs/rag.md`,
README feature entry, gitignore for chroma_db/__pycache__. End-to-end CLI ingest+search
verified (model all-MiniLM-L6-v2, chromadb 1.5.9 PersistentClient).
**State:** Feature complete + documented + tested. pytest is dev-only (uv pip install pytest).
**Next:** Possible: document chunking for long policies; multi-agent routing/risk layer
on top of search; persist requirements-dev. Not committed yet (commit on user request).

## 2026-06-17 — Agent bootstrap
**Done:** Created CLAUDE.md operating rules, SessionStart continuity hook, LEARNINGS +
SESSION_LOG persistence, skills (remark, document-feature, cleanup-experiment), and
routing subagents (task-router, feature-implementer, feature-documenter, experiment-cleaner).
**State:** Project has RAG bootstrap in `src/ingestion/rag/index.py` (ChromaDB +
sentence-transformers, scratch/experimental). No `tests/` or `docs/` yet.
**Next:** Refactor `src/ingestion/rag/index.py` into a modular feature (rule 4),
strip experiment code (rule 5), add docs (rule 2).
