# Frontend — AML Compliance Platform

React + Vite + TypeScript UI for interacting with the backend (import documents, search).

## Run

```bash
cp .env.example .env          # point VITE_API_URL at the backend (default :8000)
npm install
npm run dev                   # http://localhost:5173
```

The backend must be running (see `../backend`). CORS allows `http://localhost:5173`.

## Structure

- `src/api.ts` — typed client for the backend.
- `src/components/UploadDocs.tsx` — upload one or more PDFs (policy/action) with WebSocket progress.
- `src/components/SearchDocs.tsx` — search the corpus with MLflow tracking.
- `src/components/ChatDocs.tsx` — interactive compliance chat with SSE streaming answers and collapsible reasoning panels.
- `src/components/ManageDatabase.tsx` — clear the database (with confirm).
- `src/App.tsx` — composes the views.

## Planned

CSV import (financial actions) — add an endpoint + an `UploadCsv` component alongside.
