# Augmented Generation

Generates grounded answers from retrieved context using a **local** LLM via Ollama.
Lives in `backend/app/generation/`. Completes the RAG loop: retrieve → augment prompt →
generate with citations.

## Prerequisite

[Ollama](https://ollama.com) running locally with the model pulled:

```bash
ollama serve             # if not already running
ollama pull qwen3.5:2b   # default model — small, fast on CPU, supports tool calling
```

Override via env: `OLLAMA_MODEL`, `OLLAMA_BASE_URL`.

`qwen3.5:2b` is the default because it stays responsive on CPU-only hosts and supports
native tool calling (for the planned agent layer); `gemma`-family models do not. Latency
is bounded by `GenerationConfig`: `num_predict` (max output tokens), `num_ctx` (context
window), and `keep_alive` (keeps the model resident so it is not reloaded per request).

## Usage

### API

```bash
curl -X POST http://localhost:8000/rag/answer \
  -H 'content-type: application/json' \
  -d '{"query": "What is the cash transaction reporting threshold?", "k": 3}'
```

Response:
```json
{
  "answer": "A Currency Transaction Report must be filed for cash over 10,000 USD ... [policy-ctr].",
  "citations": [{"id": "policy-ctr", "source": "bsa.pdf", "page": 1, "score": 0.59}],
  "used_context": true
}
```

Returns **503** if Ollama is unreachable.

### Streaming (SSE)

`POST /rag/answer/stream` returns the same answer token-by-token as Server-Sent Events —
use it for interactive UIs so text appears immediately. Frames: `token` `{"text": ...}`
repeatedly, then `done` `{"citations": [...], "used_context": bool}`, or `error`
`{"message": ...}` on failure. Request body matches `/rag/answer`. Frontend consumption
guide (fetch + ReadableStream, since `EventSource` can't POST) is in `frontend_spec.md`.

```bash
curl -N -X POST http://localhost:8000/rag/answer/stream \
  -H 'content-type: application/json' \
  -d '{"query": "What is the cash transaction reporting threshold?", "k": 4}'
```

### Python

```python
from app.ingestion.rag import build_rag
from app.generation import build_answer_generator

gen = build_answer_generator(build_rag())
answer = gen.generate("enhanced due diligence for PEPs?", k=3)
print(answer.answer, answer.citations)
```

## Design

- `prompt.py` — `build_prompt(query, results)`: pure; instructs the model to answer ONLY
  from context, cite by `[id]`, and admit when context is insufficient.
- `generator.py` — `AnswerGenerator` depends on a `search_fn`, a `complete_fn`
  (`str -> str`), and an optional `stream_fn` (`str -> Iterator[str]`), so it is decoupled
  from both the vector store and the LLM and is unit-tested with fakes. `generate` returns
  an `Answer`; `stream` returns a `StreamedAnswer` (citations known up front, text as a
  token iterator). `Answer` carries `citations` + `used_context`.
- `config.py` — `GenerationConfig` (model, base_url, temperature); env-overridable.
- `build_answer_generator(rag, config)` wires a `RagSystem` + LangChain `ChatOllama`.

The API offloads the blocking LLM call with `asyncio.to_thread` so the event loop (and the
WebSocket progress gateway) stays responsive.

## Limitations / Next

- Synchronous single-shot answer (no streaming tokens yet).
- Evaluation of generation quality (RAG Triad: groundedness, answer relevance, context
  relevance) is the next step — see `docs/evaluation.md` and task #3.
