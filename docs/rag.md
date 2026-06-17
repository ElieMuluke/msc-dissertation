# AML RAG System

Ingest anti-money-laundering **policies** and financial **actions**, then search them
semantically. Lives in `backend/app/ingestion/rag/`. Built on **LangChain** (Chroma vector store
+ sentence-transformers embeddings).

## What it does

Embeds each document with a sentence-transformers model and stores the vectors in an
on-disk Chroma collection via LangChain. A query is embedded the same way and matched by
cosine similarity. Results can be filtered to one document type (policy or action).

## Usage

### Python

```python
from app.ingestion.rag import build_rag, Document, DocumentType

rag = build_rag()  # defaults: ./chroma_db, model all-MiniLM-L6-v2

rag.ingest([
    Document("p1", "File a CTR for cash over 10,000 in one day.", DocumentType.POLICY,
             {"jurisdiction": "US", "regulation": "BSA"}),
    Document("a1", "Nine cash deposits of 9,500 across three branches same day.",
             DocumentType.ACTION, {"account": "ACC-1001", "risk": "high"}),
])

for hit in rag.search("structuring deposits below reporting limit", k=3):
    print(hit.score, hit.doc_type.value, hit.id, hit.text)

rag.search("cash reporting threshold", doc_type=DocumentType.POLICY)  # restrict to one kind
```

### Ingest real PDF policies

```python
from app.ingestion.rag import build_rag, load_pdfs, DocumentType, RagConfig

rag = build_rag(RagConfig(chunk_size=1000))          # chunk long pages
docs = load_pdfs("policies/", DocumentType.POLICY)   # a file or a directory of PDFs
rag.ingest(docs)
```

`load_pdfs` produces one `Document` per page with `source` filename and `page` number in
metadata (regulatory traceability); ids are `<filename>-p<page>`.

### CLI

```bash
python -m app.ingestion.rag.cli ingest data/aml_sample.json
python -m app.ingestion.rag.cli ingest-pdf policies/ --type policy
python -m app.ingestion.rag.cli search "cash reporting threshold" -k 3
python -m app.ingestion.rag.cli search "wire to shell company" --type action
```

A ready-made JSON corpus is in `data/aml_sample.json`.

## Public API

Exported from `backend/app/ingestion/rag/__init__.py`:

| Symbol | Purpose |
| --- | --- |
| `build_rag(config=None) -> RagSystem` | Wire embeddings + Chroma into a ready system. |
| `load_pdfs(path, doc_type=POLICY, metadata=None) -> list[Document]` | Load a PDF file or directory into per-page documents. |
| `RagSystem.ingest(documents) -> int` | Embed and persist documents (upsert by id). |
| `RagSystem.search(query, k=5, doc_type=None) -> list[SearchResult]` | Top-k matches. |
| `RagSystem.as_retriever(**kwargs)` | LangChain retriever for downstream LLM chains/agents. |
| `Document` | Ingestable unit: `id, text, doc_type, metadata`. |
| `DocumentType` | `POLICY` / `ACTION`. |
| `SearchResult` | `id, text, doc_type, metadata, score` (score in `[0,1]`). |
| `RagConfig` | `persist_dir, collection_name, embedding_model, distance, chunk_size, chunk_overlap`. |

## Design notes

- **Decoupled domain types**: `Document`/`DocumentType`/`SearchResult` are plain
  dataclasses, independent of LangChain. Application code never imports LangChain, so the
  framework or store can be swapped without touching callers.
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

- Single collection; separation beyond the `doc_type` filter is not modelled.
- No LLM answer-generation yet — `as_retriever()` is the hook for it.
