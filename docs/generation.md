# Augmented Generation

Generates grounded answers from retrieved context using a **local** LLM via Ollama.
Lives in `backend/app/generation/`. Completes the RAG loop: retrieve → augment prompt →
generate with citations.

## Prerequisite

[Ollama](https://ollama.com) running locally with the model pulled:

```bash
ollama serve            # if not already running
ollama pull gemma4:e2b  # default model
```

Override via env: `OLLAMA_MODEL`, `OLLAMA_BASE_URL`.

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
- `generator.py` — `AnswerGenerator` depends on a `search_fn` and a `complete_fn`
  (`str -> str`), so it is decoupled from both the vector store and the LLM and is
  unit-tested with fakes. `Answer` carries `citations` + `used_context`.
- `config.py` — `GenerationConfig` (model, base_url, temperature); env-overridable.
- `build_answer_generator(rag, config)` wires a `RagSystem` + LangChain `ChatOllama`.

The API offloads the blocking LLM call with `asyncio.to_thread` so the event loop (and the
WebSocket progress gateway) stays responsive.

## Limitations / Next

- Synchronous single-shot answer (no streaming tokens yet).
- Evaluation of generation quality (RAG Triad: groundedness, answer relevance, context
  relevance) is the next step — see `docs/evaluation.md` and task #3.
