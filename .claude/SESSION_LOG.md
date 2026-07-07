# SESSION LOG — Continuity

Loaded into context every session. Update before wrapping up. Newest entry at top.

Format:
```
## <YYYY-MM-DD HH:MM> — <session focus>
**Done:** <what got finished>
**State:** <current state of the code / repo>
**Next:** <the next step to resume from>
```

## 2026-07-07 — Judge output repair + per-topic adherence classification
**Done:** Follow-up to 07-06: a fresh full run still lost 4/57 context_recall + 7/64
topic-adherence samples to NaN. Root causes (confirmed in ragas 0.2.15 source): (a) judge
emits `"attributed": 0.5` — valid JSON but ragas's pydantic field is `int`; the failure
then triggers ragas's `FixOutputFormat` retry, which is broken with a JSON-constrained
judge (expects `{"text":...}` back; produces the mangled "Invalid json output" strings).
(b) Stock TopicAdherenceScore classifies all N extracted topics in ONE judge call; small
judges return the wrong count → broadcast ValueError. Fixes: (1) `_repair_judge_json` +
`_JudgeChatOllama` in ragas_run.py — repairs invalid/double-encoded JSON (`json-repair`
dep added) and coerces fractional binary verdicts (user-approved policy: **0.5 → 0**,
conservative, disclosed in docs) so first-pass parse succeeds and the broken fixer never
engages. (2) `_SafeTopicAdherenceScore` now classifies one topic per judge call (same
prompts/math as ragas) — count mismatch structurally impossible; no-topics (greeting) →
NaN + warning. 6 new tests; suite 73 pass. Live smoke vs mistral-nemo judge OK.
docs/evaluation.md updated. Env note: OLLAMA_MODEL now resolves to `deepseek-r1:14b`,
RAGAS_JUDGE_MODEL=mistral-nemo:latest.
**State:** Bounded verification run (`--limit 6`, aml_corpus) launched — check it produced
zero OutputParserException/broadcast errors and 0 NaN counts. All changes uncommitted.
**Next:** If bounded run clean → user runs the real comparisons (`--collection
aml_sections_a`, `aml_sections_b`, `aml_sections_b --bm25-weight 0.3`) and builds the
before/after table vs the aml_corpus baseline in MLflow experiment rag-ragas.

## 2026-07-06 — Eval-run forensics + judge robustness
**Done:** (1) **Root-caused why the 07-06 full run matched the baseline exactly**: the
section-chunked corpora live in separate Chroma collections (`aml_sections_a` = plain,
3121 chunks; `aml_sections_b` = parent-context prefix, 3220) while `ragas_run` defaults to
`--collection aml_corpus` (old page-window chunks, 3015) and `--bm25-weight 0.0` — the run
evaluated the unchanged pipeline; chunking/hybrid were never active. No reranker exists in
the codebase. Runner now prints the active config + store fingerprint (chunk count,
detected chunking style) at startup, logs `n_chunks`/`chunk_style` to MLflow, aborts on an
empty collection. (2) Judge JSON parse failures (`OutputParserException` → NaN) fixed with
`format="json"` (Ollama grammar-constrained decoding) on the judge ChatOllama; smoke-tested
live through a real RAGAS prompt. (3) TopicAdherence shape crashes (`ValueError` broadcast
(7,)vs(19,), `TypeError` bitwise_and) — judge classifying against the wrong list — now
skip-and-log: safe subclass in `topic_adherence_metrics()` scores NaN + warns with the
question. 2 new regression tests; suite 67 pass. docs/evaluation.md updated (also fixed
stale `llama3.2:3b` default). Note: shell env sets `RAGAS_JUDGE_MODEL=mistral-nemo:latest`
(independent family — good).
**State:** Fixes in working tree (uncommitted, along with the earlier section-chunking +
hybrid work). The genuine "after" eval has NOT run yet.
**Next:** Run the real comparison: `python -m app.evaluation.ragas_run --k 4 --collection
aml_sections_a` (chunking only), then `--collection aml_sections_b`, then add
`--bm25-weight 0.3` — build the before/after table from those MLflow runs vs the existing
baseline. Verify startup line says `section chunking` before letting a run continue.

## 2026-07-01 — RAGAS eval audit hardening (Gaps #2–#8)
**Done:** Audited RAGAS eval, then fixed the gaps. (#2) `datasets/golden_set_v1.jsonl` — 57
hand-verified triples grounded in the REAL corpus (chroma_db `aml_corpus`: FATF/JMLSG PDFs),
44 clear / 7 ambiguous / 6 honest no_answer; runner populates `retrieved_contexts` live.
(#3/#4) `TopicAdherenceScore` P/R/F1 wired (`topic_adherence_metrics`, one instance per mode),
`REFERENCE_TOPICS` (20 AML topics), `datasets/out_of_scope_v1.jsonl` (13 off-topic incl.
prompt-injection). (#5) judge config independent-by-recommendation + `_warn_if_self_eval`
family check; judge model+temp logged. (#6/#7/#8) `run_ragas` uses public `to_pandas()`,
per-query CSV+JSON to `eval_results/`, NaN counted/warned/excluded (`RagasResult.nan_counts`).
`ragas_run.py` rewritten to use the real retriever (no throwaway store) + golden set + topic
set. Updated `docs/evaluation.md`, `__init__.py` exports, FEATURES F23. Unit tests 9/9.
**State:** Code done + verified. Key runtime finding: CPU-only Ollama is the bottleneck —
gen ~80s/query; `llama3.2:3b` judge unusable (NaN via JSON parse-failure, 37min/sample);
`qwen2.5:3b` judge works (valid scores, ~64s/metric) but same family as the qwen generator
→ self-eval (user accepted, disclose in dissertation). Full 57+64 run = many hours. A bounded
`--limit 6` run (experiment `rag-ragas-bounded`, generator+judge qwen2.5:3b) was launched to
produce a real sample summary table.
**Next:** Collect bounded-run summary table + flag suspicious values; then run the FULL set on
a GPU/faster host (or overnight): `OLLAMA_MODEL=<qwen-gen> RAGAS_JUDGE_MODEL=<independent, e.g.
gemma2:9b> python -m app.evaluation.ragas_run --k 4`. Consider deleting superseded toy sets
`datasets/ragas_questions.jsonl` + `ragas_corpus.json` (now unreferenced).

## 2026-06-25 — Fix empty stream + collapsible thinking channel
**Done:** Chat stream froze with citations but no text. Root cause: `qwen3.5:2b` is a Qwen3
thinking model — reasoning streams on `chunk.additional_kwargs['reasoning_content']`, not
`chunk.content`, and fills the whole `num_predict` budget so the answer never emits.
(1) Fix: added `GenerationConfig.reasoning` (env `OLLAMA_REASONING`, default **off**) →
`reasoning=False` on ChatOllama makes the answer stream straight to `content`. `num_predict`
now env `OLLAMA_NUM_PREDICT` (default 512). (2) Thinking feature: `build_stream_completion`
now yields tagged `StreamChunk(kind, text)` (`thinking`|`answer`); `StreamedAnswer.tokens`
→ `.chunks`; route emits separate `thinking` + `token` SSE frames. Exported `StreamChunk`.
Updated `test_answer_stream` (asserts both channels); 12 pass. Frontend contract updated in
`frontend_spec.md` §1 (thinking event + collapsible `<details>` panel). FEATURES F21/F22.
**State:** Backend supports thinking channel, gated off. Reasoning ON is impractical on the
current CPU model (verified: 220s, 3830+ chars thinking, zero answer — runaway thinker).
**Next:** Decide reasoning-capable model before enabling `OLLAMA_REASONING` (e.g. a model
whose reasoning converges, or GPU). Frontend (Gemini) wires the collapsible panel per spec.

## 2026-06-18 — Streaming answers (SSE)
**Done:** Added `POST /rag/answer/stream` — SSE token streaming for perceived latency.
Generator: optional `stream_fn` injected; `AnswerGenerator.stream()` → `StreamedAnswer`
(citations up front, tokens as iterator); `build_stream_completion` via `llm.stream()`;
DRY'd ChatOllama construction into `_build_chat_ollama`. Route emits `token`/`done`/`error`
frames, runs in threadpool (sync generator) so blocking LLM never blocks event loop.
Exported `StreamedAnswer`/`build_stream_completion`. New test `test_answer_stream`; 50 pass.
Wrote `frontend_spec.md` (backend→frontend contract: SSE schema + fetch/ReadableStream TS
guide, since EventSource can't POST). Updated docs/generation.md, FEATURES F18.
**State:** Backend streaming complete + tested. `/rag/answer` (non-stream) unchanged.
**Next:** Frontend (Gemini) implements `frontend_spec.md` §1. Then agents (qwen tool calls).

## 2026-06-17 — LLM latency optimization
**Done:** Slow answers root-caused to hardware, not RAG: CPU-only, ~2GB RAM free, model
`gemma4:e2b`=7.2GB → swapping/reloading per call. Fixes: default model → `qwen3.5:4b`
(3.4GB, already pulled; fast on CPU, **supports tool calling** for future agents; gemma
does not). Added `num_predict=384`, `num_ctx=4096`, `keep_alive=30m` to GenerationConfig +
passed to ChatOllama. RagConfig `chunk_size 0→900`, `overlap 200→150` (smaller prompts =
less CPU prefill). AnswerRequest default `k 5→4`. Suite 49 pass. docs/generation.md updated.
**User action:** free RAM; **re-ingest** corpus (existing chroma_db was ingested unchunked —
chunking only applies to new ingests).
**State:** Config-only optimization, no API shape change. Tests green.
**Next:** Optional streaming (`/rag/answer` → SSE) for perceived latency. Then F12 / agents.

## 2026-06-17 — PDF ingestion text-cleanup (backend spec §6)
**Done:** Added pure `clean_pdf_text` in new `app/ingestion/rag/cleaning.py` (SRP — own
module, no langchain dep), applied to each page in `load_pdfs` before building Documents.
Glyph/ligature mapping, control-char strip, hyphen line-join, single-break→space (paragraph
`\n\n` preserved via lookarounds), space collapse. **Fixed spec bug:** narrowed control
regex `\x7f-\xff`→`\x7f-\x9f` so the inserted `©` and accented Latin-1 chars survive. 6
unit tests `tests/test_cleaning.py`. Suite 49 pass. Updated backend_spec §6, FEATURES F17,
docs/rag.md.
**State:** Feature complete + documented + tested. Backend matches backend_spec §1–6.
**Next:** F12 frontend (Gemini-owned). Backend idle — await next backend_spec item.

## 2026-06-17 — `/health` connectivity (backend spec §5)
**Done:** Implemented real `/health` (was stub `{status:ok}`). Added `RagSystem.ping()`
(Chroma `get(limit=1)`) and `build_llm_ping()` in generation pkg (HTTP GET
`{base_url}/api/tags`, 2s timeout) — both injected via `get_rag`/`get_llm_ping` deps, no
collection/ChatOllama leaked. `HealthResponse` schema; `status` ok/degraded. 2 new API
tests (ok + llm-down). Full suite 43 pass. Updated backend_spec §5, FEATURES F15.
**State:** Backend feature-complete vs backend_spec (§1–5 ✅). All tests green.
**Next:** F12 — run frontend (`npm install`) end-to-end; wire header badges to `/health`.

---

## 2026-06-17 — RAG Triad eval (F10, task #3)
**Done:** `app/evaluation/triad.py`: reference-free LLM-judge triad — pure prompt builders
(context_relevance/groundedness/answer_relevance), `parse_score` (regex + clamp [0,1]),
`make_llm_judge(complete_fn)`, `evaluate_triad(records, judge_fn)` (judge injected → pure,
fake-testable). `triad_run.py` CLI: ingest corpus → generate answers → judge → log MLflow
experiment `rag-triad`. Datasets triad_corpus.json + triad_questions.jsonl. Refactored
generation: added `build_completion` (DRY, shared by generator + judge), `Answer.contexts`
field (retrieved texts, needed for judging). Tests test_triad.py (6, fake judge). Suite 41
pass. REAL run (Ollama gemma judge): context_relevance 0.575, groundedness 1.0,
answer_relevance 1.0 → logged. docs/evaluation.md triad section, FEATURES F10 ✅. Task #3 done.
**State:** Eval complete on both axes — retrieval (rag-retrieval) + generation (rag-triad) +
live search monitoring (rag-search-monitoring), all in MLflow. Triad run needs Ollama (slow:
generate+judge LLM calls). User also marked backend_spec §4 (generation) ✅.
**Next:** Optional — token streaming, frontend Ask/Chat view, live generation monitoring,
restore backend/data corpus for retrieval eval default path.

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
