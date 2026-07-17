# Frontend Specifications (Backend → Frontend)

Capabilities the **backend** exposes that the **frontend** should implement against. This
is the mirror of `backend_spec.md`: there the frontend records what it needs from the
backend; here the backend documents how the frontend should consume a backend capability.

Status: 🔵 to implement · 🟡 in progress · ✅ done

> **⚠️ Breaking change (2026-07-11): `POST /tabular/ingest`, `POST /tabular/ingest/local`,
> and `POST /rag/documents/pdf` now stream Server-Sent Events instead of broadcasting over
> `/ws`.** The shared `/ws` WebSocket gateway (`app/realtime.py`, `event: ingestion_progress`)
> has been **deleted entirely** — the backend no longer exposes a `/ws` route at all. These
> three endpoints now respond with `text/event-stream` and stream `progress`/`error`/`done`
> frames on the request itself, the same pattern `POST /rag/answer/stream` already used for
> LLM token streaming. `UploadTabular.tsx`'s `useWebSocket`/`handleWsMessage` subscription and
> the equivalent in `UploadDocs.tsx` need to switch from listening on the shared socket to
> reading each of these endpoints' own response as a stream — see §5 below for the full
> shape and a reference implementation to copy from `streamAnswer` in `api.ts`. Also:
> `POST /tabular/ingest`/`/ingest/local` no longer return a single JSON body on success —
> the final result now arrives as the `done` SSE frame instead.

---

## 6. `GET /tabular/counts` — don't swallow fetch errors as "no data"

**Status**: ✅ Done (implemented retry state and manual retry button).

### Why
`UploadTabular.tsx`'s `fetchCounts()` (mount + post-ingest) currently does
`catch (err) { console.warn(...) }` and leaves `counts` as `null`, which renders the same
as a genuinely-empty `{"accounts": 0, "transactions": 0}` response — a failed request and
an empty dataset are indistinguishable to the user. At real dataset scale (100M+ rows in
`transactions`), `/tabular/counts` is more likely to be slow or occasionally fail than on a
toy dataset, so this indistinguishability turned into a real user-facing bug: uploaded data
existed the whole time, but a slow/failed counts fetch made the UI say "no tabular data."

### Ask
On a failed `/tabular/counts` fetch, render a distinct state — e.g. "Couldn't load counts
(retry)" — instead of falling through to the same UI as zero rows. A manual retry
action (button, not just relying on next mount) would also help, since currently the only
retriggers are page load and a successful ingest.

---

## 5. SSE Progress for Tabular + PDF Ingestion — replaces `/ws`

**Status**: ✅ Done (implemented SSE progress listener in api.ts, updated components to use SSE and deleted WebSocket hook).
section is the frontend follow-up. Supersedes the `/ws`-based progress description
previously implied by §2/§3/§4 below (those still describe the request/response *shapes*
correctly except for the transport itself, which is now SSE per this section).

### Why

The old design broadcast every ingestion's progress to *every* connected `/ws` client, and
each upload component filtered incoming frames by matching `filename` against its own
`activeUploadsRef`. That's more moving parts than the job needs — progress for one upload
only matters to the request that started it. `POST /rag/answer/stream` already established
a simpler pattern in this codebase: stream progress as SSE on the response of the very
request that needs it. This backend change generalizes that pattern to file ingestion.

### Affected endpoints

| Endpoint | Old | New |
| --- | --- | --- |
| `POST /tabular/ingest` | JSON body + `/ws` frames | `text/event-stream`, frames below |
| `POST /tabular/ingest/local` | JSON body + `/ws` frames | `text/event-stream`, frames below |
| `POST /rag/documents/pdf` | JSON body + `/ws` frames | `text/event-stream`, frames below |

`POST /tabular/ingest/text` is unaffected — still a single JSON request/response (pasted
text ingests synchronously, no progress needed).

### Frame shapes

**Tabular** (`/tabular/ingest`, `/tabular/ingest/local`) — one `progress` frame per
upload-percent milestone, per file:
```
event: progress
data: {"filename": "HI-Large_accounts.csv", "progress": 10, "status": "uploading"}

event: progress
data: {"filename": "HI-Large_accounts.csv", "progress": 47, "status": "inserting"}
```
`progress` is now computed from **bytes read**, not exact row count (see `docs/tabular.md`
for why) — expect more frequent, smoothly-incrementing updates rather than big jumps.
On failure, instead of further `progress` frames for that file:
```
event: error
data: {"filename": "HI-Large_accounts.csv", "message": "Expected one of ('.csv',) for accounts: bad.txt"}
```
An `error` frame stops processing of any remaining files in the same multi-file request —
render it and stop, the same way you'd handle the old `/ws` `status: "error"` frame with
`error_message`. Once every file in the request has ingested successfully, one final frame
ends the stream:
```
event: done
data: {"ingested": 2126855, "data_type": "accounts"}
```
`ingested` here is what the old JSON response body used to carry — read it off this frame
instead of a response body, since there no longer is one beyond the stream itself.

**PDF** (`/rag/documents/pdf`) — same `progress`/`error`/`done` frame shape, `status` one of
`"uploading"` (10%) → `"parsing"` (40%) → `"vectorizing"` (70%) → `"completed"` (100%, fixed
milestones, not byte-based — PDF parsing doesn't have a meaningful "bytes done" concept the
way CSV row-streaming does); `done` frame is `{"ingested": <total pages ingested>}`.

### Reference implementation

Same client-side pattern as `streamAnswer` (`api.ts`, documented in §1 above) — `fetch()`,
read `res.body.getReader()`, split on blank lines, parse `event:`/`data:` lines per frame.
The only difference from `streamAnswer`: these three endpoints take a request body first
(`FormData` for the two upload-style tabular/PDF endpoints, JSON for `/ingest/local`) rather
than JSON only, but the response-reading side is identical. Minimal sketch:
```ts
export async function ingestTabular(
  dataType: "accounts" | "transactions" | "patterns",
  files: File[],
  onProgress: (filename: string, pct: number, status: string) => void,
): Promise<number> {
  const form = new FormData();
  form.append("data_type", dataType);
  files.forEach((f) => form.append("files", f));

  const res = await fetch(`${API_URL}/tabular/ingest`, { method: "POST", body: form });
  if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let total = 0;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      if (!frame.trim()) continue;
      let event = "message", data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "progress") onProgress(payload.filename, payload.progress, payload.status);
      else if (event === "error") throw new Error(`${payload.filename}: ${payload.message}`);
      else if (event === "done") total = payload.ingested;
    }
  }
  return total;
}
```
Apply the same shape to `ingestTabularLocal` (JSON body instead of `FormData`) and the PDF
upload call. `UploadTabular.tsx`/`UploadDocs.tsx` no longer need `useWebSocket`/
`activeUploadsRef` filtering at all — each component's own `fetch` call now owns its own
progress stream directly, one fewer layer of indirection.

---

## 4. Paste/Type CSV Text Tabular Ingestion — `POST /tabular/ingest/text`

**Status**: ✅ Implemented. `UploadTabular.tsx` has a "Paste" method with a textarea,
`422` error-list rendering, and `ingestTabularText` in `api.ts`.

Add a way for a user to paste or type CSV/TXT rows directly into a text field and ingest
them, without needing to save the text to a file first. The whole payload is validated as
well-formed *before* any database write — a malformed paste returns a list of every
problem found and inserts nothing, so the DB can never end up with a partial/corrupt
insert from bad pasted data. See `docs/tabular.md` (new "`POST /tabular/ingest/text`"
subsection) for the full backend-side guarantee.

### Request
* **Method / URL**: `POST /tabular/ingest/text`
* **Body**: `application/json`
```json
{ "data_type": "accounts", "csv_text": "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\nBank A,001,111,E1,Alice\n" }
```
* `data_type`: one of `accounts` | `transactions` | `patterns` (same selector as the
  existing upload UI — reuse it).
* `csv_text`: the raw text as typed/pasted, including the header row for `accounts`/
  `transactions` (`patterns` text has no header, same block format as
  `HI-Large_Patterns.txt` — see `docs/tabular.md`).

### Response (success)
Same shape as the other ingest endpoints:
```json
{ "ingested": 1, "data_type": "accounts" }
```

### Response (validation failure) — `422`
```json
{ "detail": ["Missing required column(s) for accounts: Bank ID", "..."] }
```
`detail` is a **list of strings**, not a single message — render *all* of them (e.g. a
bullet list), not just the first. On `422`, nothing was inserted; the counts display
should not change.

### Suggested UX
* A textarea (paste/type CSV or TXT rows) + the same `data_type` selector already used
  for file upload, + a submit button.
* On `422`: show the full error list inline (e.g. above or below the textarea) and leave
  the textarea's contents untouched, so the user can fix the text and resubmit without
  retyping.
* On success (`200`): clear the textarea and refresh the counts display, same as the
  existing upload flow.
* No `/ws` progress frames for this endpoint — it responds synchronously (pasted text is
  expected to be small), so no progress bar/polling is needed here.

---

## 3. Local-path Tabular Ingestion (large files) — `POST /tabular/ingest/local`

**Status**: ✅ Implemented. `UploadTabular.tsx` has a "Path" method with a server-path
text input and `ingestTabularLocal` in `api.ts`.

`POST /tabular/ingest` (multipart upload) is fine for small/medium files, but very large
source files (the real `HI-Large_Trans.csv` is ~17GB) are slow and, on hosts where `/tmp`
is a small tmpfs, can fail outright with `{"detail":"There was an error parsing the body"}`
(disk fills up mid-upload). For files already sitting on the machine running the backend,
add an alternative path in the tabular upload UI: a text input for a **server-local file
path** instead of a file picker, submitting to this endpoint instead of `/tabular/ingest`.
No multipart body, no upload — the backend reads the file directly off its own disk.

### Request
* **Method / URL**: `POST /tabular/ingest/local`
* **Body**: `application/json`
```json
{ "data_type": "transactions", "path": "/absolute/path/on/server/HI-Large_Trans.csv" }
```
* `data_type`: one of `accounts` | `transactions` | `patterns` (same as `/tabular/ingest`).
* `path`: absolute path on the **backend's** filesystem (not the browser's). `400` if the
  path doesn't exist or its extension doesn't match `data_type` (same rule as the upload
  endpoint: `.csv` for accounts/transactions; `.csv`/`.txt` for patterns).

### Response
Same shape as `POST /tabular/ingest`:
```json
{ "ingested": 8000000, "data_type": "transactions" }
```

### Progress
Broadcasts the exact same `/ws` progress frames as `POST /tabular/ingest` (`uploading` →
`inserting` → `completed`/`error`, keyed by the file's basename) — reuse the existing
WebSocket handling in `UploadTabular.tsx`, just triggered from this endpoint instead.

Suggested UI: a small "Ingest from server path" toggle/tab next to the existing
drag-and-drop uploader, with a text input for the path and the same submit/progress UX.

---

## 2. Tabular Data Ingestion UI (accounts / transactions / patterns)

**Status**: ✅ Implemented. Backend ready — `POST /tabular/ingest` and `GET
/tabular/counts` via `TabularSystem` (`app/ingestion/tabular/`,
`app/api/routes/tabular.py`). See `docs/tabular.md` for the ingested file shapes, ORM
schema, and streaming/batched-insert design.

Build a "select which data type, then upload" UI for the IBM/Kaggle "HI-Large" AML
dataset: a type selector (`accounts` | `transactions` | `patterns`) followed by a file
upload, plus a small volumes display (row counts per table).

### Ingest

* **Endpoint**: `POST /tabular/ingest`
* **Request Type**: `multipart/form-data`
* **Form fields**:
  * `data_type` (string, required): one of `accounts` | `transactions` | `patterns`.
  * `files` (one or more file uploads, required): `.csv` for `accounts`/`transactions`;
    `.csv` or `.txt` for `patterns`. A file with an unexpected extension for the chosen
    `data_type` returns `400`.
* **Response Type**: `application/json`

### `TabularIngestResponse` JSON Schema:
```json
{
  "ingested": 1000,
  "data_type": "accounts"
}
```

`ingested` is the number of rows newly inserted across all uploaded files in the call.
Re-uploading the same `accounts` file is idempotent (unique on bank/account number) and
reports `0` newly-inserted rows on repeat; `transactions`/`patterns` are always inserted
(no dedup — legitimate duplicate transactions can occur).

### Counts

* **Endpoint**: `GET /tabular/counts`
* **Response Type**: `application/json`

### `TabularCounts` JSON Schema:
```json
{
  "accounts": 1000,
  "transactions": 50000
}
```

Suggested UI: show these counts near the upload control so the user sees ingested
volumes update after each upload.

---

## 1. Streaming Answers (SSE) — `POST /rag/answer/stream`

**Status**: Token streaming ✅ done on frontend. **✅ Collapsible "thinking" panel** is now done on the frontend (using `thinking` event + Collapsible thinking UX + `onThinking` handler). Backend ✅ live (thinking gated by `OLLAMA_REASONING`, default off — panel renders only when reasoning is on, so it remains empty/hidden until enabled).

Stream a grounded compliance answer token-by-token so the user sees text appear
immediately instead of waiting for the whole answer (the model is CPU-bound and slow to
finish a full response). Use this instead of `POST /rag/answer` wherever the answer is
shown to a user; keep `/rag/answer` only for non-interactive/programmatic callers.

### Endpoint
* **Method / URL**: `POST /rag/answer/stream`
* **Response**: `text/event-stream` (Server-Sent Events), chunked.
* **Request body** (same schema as `/rag/answer`):
```json
{
  "query": "What are the suspicious transaction thresholds?",
  "k": 4
}
```

### Event frames
Each SSE frame is `event: <type>\ndata: <json>\n\n`. Four types:

| event      | data                                              | when |
| ---------- | ------------------------------------------------- | ---- |
| `thinking` | `{ "text": "..." }`                               | repeatedly, **before** the answer — the model's reasoning trace. Zero or more (only when reasoning is enabled server-side). |
| `token`    | `{ "text": "..." }`                               | repeatedly, as the answer generates |
| `done`     | `{ "citations": [Citation], "used_context": bool }` | once, after the last token |
| `error`    | `{ "message": "..." }`                             | instead of `done` if generation fails |

Ordering guarantee: `thinking*` → `token*` → (`done` | `error`).

`Citation` matches the non-streaming `AnswerResponse.citations` item:
```json
{ "id": "1", "source": "anti_money_laundering_act.pdf", "page": 12, "score": 0.895 }
```

**Render contract**: append every `thinking.text` to a **collapsible "reasoning" panel**
(collapsed by default) and every `token.text` to the **answer body**, each in arrival
order. When `done` arrives, render the citations (and a "no context" hint when
`used_context` is `false`). On `error`, stop and show `message`.

**Collapsible thinking UX:**
* Render the "Show reasoning" toggle only if at least one `thinking` frame arrived —
  absence of `thinking` frames means reasoning is off, so show no toggle. No request flag
  needed.
* Keep the panel collapsed by default; optionally auto-collapse it once the first `token`
  arrives so the answer is the focus.
* `thinking` text is plain reasoning prose (may contain newlines); render as
  preformatted/whitespace-preserving.

### Why not `EventSource`
The browser `EventSource` API only does **GET** and can't send a JSON body. This endpoint
is `POST`, so consume it with `fetch` + a `ReadableStream` reader and parse SSE frames
manually (small, shown below).

### Reference implementation (TypeScript)
```ts
export interface Citation {
  id: string;
  source: string;
  page: number | null;
  score: number;
}

export interface StreamHandlers {
  onThinking?: (text: string) => void; // optional: reasoning trace (collapsible panel)
  onToken: (text: string) => void;
  onDone: (citations: Citation[], usedContext: boolean) => void;
  onError: (message: string) => void;
}

export async function streamAnswer(
  body: { query: string; k?: number },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/rag/answer/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    handlers.onError(`Request failed: ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? ""; // keep the trailing partial frame

    for (const frame of frames) {
      if (!frame.trim()) continue;
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "thinking") handlers.onThinking?.(payload.text);
      else if (event === "token") handlers.onToken(payload.text);
      else if (event === "done") handlers.onDone(payload.citations, payload.used_context);
      else if (event === "error") handlers.onError(payload.message);
    }
  }
}
```

### React usage sketch
```tsx
const [thinking, setThinking] = useState("");
const [answer, setAnswer] = useState("");
const [citations, setCitations] = useState<Citation[]>([]);

await streamAnswer(
  { query, k: 4 },
  {
    onThinking: (t) => setThinking((prev) => prev + t),
    onToken: (t) => setAnswer((prev) => prev + t),
    onDone: (cits) => setCitations(cits),
    onError: (msg) => setAnswer(`⚠️ ${msg}`),
  },
);

// Render the collapsible panel only when reasoning actually streamed:
{thinking && (
  <details>
    <summary>Show reasoning</summary>
    <pre style={{ whiteSpace: "pre-wrap" }}>{thinking}</pre>
  </details>
)}
```

### Notes
* Pass an `AbortController.signal` so navigating away / starting a new query cancels the
  in-flight stream.
* Reset `thinking`/`answer`/`citations` before starting a new stream.
* The `thinking` channel only carries data when reasoning is enabled on the backend
  (`OLLAMA_REASONING=1`); it ships **off by default** because the current local
  `qwen3.5:2b` over-thinks on CPU and starves the answer. Build the panel now against this
  contract — it simply stays empty (no toggle) until reasoning is switched on behind a
  model whose reasoning converges. No frontend change needed when it flips on.
* Dev server: Vite proxy must not buffer the stream. The backend already sends
  `Cache-Control: no-cache` and `X-Accel-Buffering: no`; if proxying, disable response
  buffering for `/rag/answer/stream`.
