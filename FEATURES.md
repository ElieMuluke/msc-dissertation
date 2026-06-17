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
| F9 | LLM answer-generation over retrieved docs | 🔵 | task #4 |
| F10 | RAG Triad generation evaluation | ⛔ | task #3; blocked by F9 |
| F11 | Frontend Tailwind restyle | ✅ | user-implemented |
| F12 | Run frontend (`npm install`) end-to-end | 🔵 | not run yet |
| F13 | Realtime ingestion progress (WebSocket `/ws`) | ✅ | spec §3; per-file frames |

Related: `backend_spec.md` (frontend↔backend API contract), in-session task list (TaskList).
