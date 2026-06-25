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
| F21 | Stream fix: empty answer (Qwen3 thinking) | ✅ | reasoning routed off `content`; `OLLAMA_REASONING` gate, default off |
| F22 | Collapsible "thinking" channel in SSE | ✅ | `thinking` SSE event; spec §7. Gated by `OLLAMA_REASONING` (model over-thinks on CPU) |

Related: `backend_spec.md` (frontend↔backend API contract), in-session task list (TaskList).
