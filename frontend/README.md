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
- `src/components/UploadDocs.tsx` — upload one or more PDFs with WebSocket progress.
- `src/components/UploadTabular.tsx` — upload structured HI-Large tabular csv/txt datasets (accounts/transactions/patterns) and view row volume statistics.
- `src/components/SearchDocs.tsx` — search the corpus with MLflow tracking.
- `src/components/ChatDocs.tsx` — interactive compliance chat with SSE streaming answers and collapsible reasoning panels.
- `src/components/ManageDatabase.tsx` — clear the database (with confirm).
- `src/App.tsx` — composes the views with responsive layouts supporting mobile, tablet, and desktop viewports.
- `docs/frontend/responsiveness.md` — detailed documentation of responsive layout breakpoints (sm, md, xl) and component behavior.

