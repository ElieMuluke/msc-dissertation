# AML RAG System

Generic document ingestion into a vector database, then semantic search over it. Lives in
`backend/app/ingestion/rag/`. Built on **LangChain** (Chroma vector store + sentence-transformers
embeddings). There is no type-based classification of documents — every document
(regulatory text, procedures, case notes, or anything else) is stored and searched the
same way.

## What it does

Embeds each document with a sentence-transformers model and stores the vectors in an
on-disk Chroma collection via LangChain. A query is embedded the same way and matched by
cosine similarity.

## Usage

### Python

```python
from app.ingestion.rag import build_rag, Document

rag = build_rag()  # defaults: ./chroma_db, model all-MiniLM-L6-v2

rag.ingest([
    Document("p1", "File a CTR for cash over 10,000 in one day.",
             {"jurisdiction": "US", "regulation": "BSA"}),
    Document("a1", "Nine cash deposits of 9,500 across three branches same day.",
             {"account": "ACC-1001", "risk": "high"}),
])

for hit in rag.search("structuring deposits below reporting limit", k=3):
    print(hit.score, hit.id, hit.text)
```

### Ingest real PDF policies

```python
from app.ingestion.rag import build_rag, load_pdfs, RagConfig

rag = build_rag(RagConfig(chunk_size=1000))  # chunk long pages
docs = load_pdfs("policies/")                # a file or a directory of PDFs
rag.ingest(docs)
```

`load_pdfs` produces one `Document` per page with `source` filename and `page` number in
metadata (regulatory traceability); ids are `<filename>-p<page>`.

Each page's text is normalized by `clean_pdf_text` (`cleaning.py`) before a `Document` is
built: mis-extracted glyphs/ligatures mapped to standard chars, control characters
stripped (printable Latin-1 like `©`/`é` preserved), hyphen line-splits rejoined, single
line breaks turned into spaces while paragraph gaps (`\n\n`) are kept, and runs of
spaces/tabs collapsed. This keeps extraction noise out of the embedding space.

### CLI

```bash
python -m app.ingestion.rag.cli ingest data/aml_sample.json
python -m app.ingestion.rag.cli ingest-pdf policies/
python -m app.ingestion.rag.cli search "cash reporting threshold" -k 3
```

A ready-made JSON corpus is in `data/aml_sample.json`.

## Public API

Exported from `backend/app/ingestion/rag/__init__.py`:

| Symbol | Purpose |
| --- | --- |
| `build_rag(config=None) -> RagSystem` | Wire embeddings + Chroma into a ready system. |
| `load_pdfs(path, metadata=None) -> list[Document]` | Load a PDF file or directory into per-page documents. |
| `RagSystem.ingest(documents) -> int` | Embed and persist documents (upsert by id). |
| `RagSystem.search(query, k=5) -> list[SearchResult]` | Top-k matches. |
| `RagSystem.scope_confidence(query) -> float` | Raw top-1 vector relevance (bypasses BM25 fusion, whose per-query min-max normalization erases absolute confidence); `0.0` on an empty store. Feeds the generation layer's out-of-scope gate. |
| `RagSystem.as_retriever(**kwargs)` | LangChain retriever for downstream LLM chains/agents. |
| `RagSystem.list_sources() -> list[SourceInfo]` | Ingested source files, aggregated by filename. |
| `RagSystem.delete_by_source(filename) -> int` | Delete all documents from one source file. |
| `RagSystem.clear()` | Delete all documents (resets the collection). |
| `RagSystem.ping() -> bool` | Whether the vector store is reachable. |
| `Document` | Ingestable unit: `id, text, metadata`. |
| `SearchResult` | `id, text, metadata, score` (score in `[0,1]`). |
| `SourceInfo` | `filename, pages, ingested_at`. |
| `RagConfig` | `persist_dir, collection_name, embedding_model, distance, chunk_size, chunk_overlap`. |

## Design notes

- **Decoupled domain types**: `Document`/`SearchResult`/`SourceInfo` are plain dataclasses,
  independent of LangChain. Application code never imports LangChain, so the framework or
  store can be swapped without touching callers.
- **Generic ingestion, no type field**: documents carry an open `metadata` dict instead of
  a fixed type enum, so callers model any distinction they need (jurisdiction, regulation,
  risk, ...) via metadata rather than a hardcoded classification baked into the system.
- **Industry-standard stack**: LangChain `Chroma` + `HuggingFaceEmbeddings`. Swapping to
  FAISS / pgvector / Pinecone is a change to `build_rag` alone.
- **Future-ready**: `as_retriever()` plugs the corpus straight into LangChain RAG chains
  and LangGraph multi-agent flows. `chunk_size`/`chunk_overlap` enable splitting long
  policies (e.g. PDFs) at ingestion.
- **Testable**: `tests/test_rag.py` runs against an in-memory Chroma with deterministic
  fake embeddings — no model download, no disk.

## Configuration

```python
from app.ingestion.rag import build_rag, RagConfig
rag = build_rag(RagConfig(persist_dir="./store", collection_name="aml", chunk_size=1000))
```

`chunk_size > 0` splits long documents into overlapping chunks; chunk ids are suffixed
`#0`, `#1`, ... so the source document stays traceable.

## Tests

```bash
python -m pytest
```

## Limitations / TODO

- Single collection; there is no built-in type/category separation — model any such
  distinction via `metadata` and filter client-side if needed.
- Answer generation lives in `app/generation/` (see `docs/generation.md`), built on top of
  `as_retriever()`/`RagSystem.search`.
