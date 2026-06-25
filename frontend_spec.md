# Frontend Specifications (Backend → Frontend)

Capabilities the **backend** exposes that the **frontend** should implement against. This
is the mirror of `backend_spec.md`: there the frontend records what it needs from the
backend; here the backend documents how the frontend should consume a backend capability.

Status: 🔵 to implement · 🟡 in progress · ✅ done

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
  "k": 4,
  "doc_type": "policy"   // optional: "policy" | "action" | null
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
  body: { query: string; k?: number; doc_type?: string | null },
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
