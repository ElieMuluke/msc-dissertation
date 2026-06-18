# Backend API Specifications for RAG Document Manager

To fully support individual document management and listing in the frontend, the backend needs to implement two new endpoints. Since the system uses FastAPI and Chroma DB as its vector store, these specifications include recommended endpoint signatures and implementation details.

---

## 1. List Ingested Documents

**Status**: ✅ Implemented — `GET /rag/documents` via `RagSystem.list_sources()`
(`app/api/routes/rag.py`, `app/ingestion/rag/rag.py`). `ingested_at` is now stamped into
metadata at ingest time. Implemented with the domain method (not a leaked `rag.collection`).

Retrieve a list of unique files that have been successfully ingested into the vector database.

* **Endpoint**: `GET /rag/documents`
* **Response Type**: `application/json`
* **Response Schema**: `list[IngestedDocument]`

### `IngestedDocument` JSON Schema:
```json
[
  {
    "filename": "anti_money_laundering_act.pdf",
    "doc_type": "policy",
    "pages": 14,
    "ingested_at": "2026-06-17T05:20:00Z"
  }
]
```

### Chroma DB Implementation Recommendation:
You can retrieve all documents currently stored in Chroma by fetching their metadata and grouping by `source` (which corresponds to the filename).
```python
@router.get("/documents", response_model=list[IngestedDocument])
def list_documents(rag: RagSystem = Depends(get_rag)) -> list[IngestedDocument]:
    # Query Chroma DB for all metadata
    collection_data = rag.collection.get(include=["metadatas"])
    metadatas = collection_data.get("metadatas", [])
    
    # Group unique sources
    unique_docs = {}
    for meta in metadatas:
        source = meta.get("source") # e.g. "anti_money_laundering_act.pdf"
        doc_type = meta.get("doc_type", "policy")
        
        if not source:
            continue
            
        if source not in unique_docs:
            unique_docs[source] = {
                "filename": Path(source).name,
                "doc_type": doc_type,
                "pages": 0,
                # Use metadata field or file modification time if stored, fallback to default
                "ingested_at": meta.get("ingested_at", "2026-06-17T00:00:00Z")
            }
        unique_docs[source]["pages"] += 1
        
    return list(unique_docs.values())
```

---

## 2. Delete Single Document

**Status**: ✅ Implemented — `DELETE /rag/documents/{filename}` via
`RagSystem.delete_by_source()`. Returns `{status, deleted_filename, chunks_removed}`;
404 when no matches.

Permanently delete all text chunks and high-dimensional vector embeddings corresponding to a specific ingested filename.

* **Endpoint**: `DELETE /rag/documents/{filename}`
* **Path Parameters**:
  * `filename` (string): The exact filename of the document to delete (e.g. `anti_money_laundering_act.pdf`).
* **Response Type**: `application/json`
* **Response Schema**:
```json
{
  "status": "success",
  "deleted_filename": "anti_money_laundering_act.pdf",
  "chunks_removed": 14
}
```

### Chroma DB Implementation Recommendation:
Chroma DB allows deleting entries by using a metadata filter query inside `collection.delete()`.
```python
@router.delete("/documents/{filename}")
def delete_document(filename: str, rag: RagSystem = Depends(get_rag)) -> dict[str, Any]:
    # Since filenames are stored in the 'source' metadata field during ingestion:
    # 1. Inspect Chroma collection details to count matches
    matches = rag.collection.get(where={"source": filename})
    match_count = len(matches.get("ids", []))
    
    if match_count == 0:
        raise HTTPException(
            status_code=404, 
            detail=f"Document '{filename}' not found in the vector database."
        )
        
    # 2. Execute deletion
    rag.collection.delete(where={"source": filename})
    
    return {
        "status": "success",
        "deleted_filename": filename,
        "chunks_removed": match_count
    }
```

---

## 3. Realtime Ingestion Progress (WebSocket Gateway)

**Status**: ✅ Implemented — `WS /ws` via `app/realtime.py` (`ConnectionManager` +
`progress_frame`). `POST /rag/documents/pdf` broadcasts per-file frames:
uploading(10) → parsing(40) → vectorizing(70) → completed(100), or error(0). Dead
connections are dropped on broadcast.

To support realistic upload and ingestion progress tracking, the backend should expose a global WebSocket gateway. This gateway can push status updates for asynchronous ingestion tasks (e.g. document upload, parsing, text chunking, and embedding generation).

* **Endpoint**: `WS /ws` (WebSocket connection gateway)
* **Message Format**: `application/json`

### Subscription / Ingestion Progress Message Schema:

When files are uploaded via standard HTTP, the backend starts the background parsing and vectorization task. Throughout the execution, the backend sends status update frames over the WebSocket to all connected clients (or specifically to the client carrying the upload session matching the task).

#### Progress Update Frame:
```json
{
  "event": "ingestion_progress",
  "data": {
    "filename": "AML_Policy_V2.pdf",
    "progress": 45,
    "status": "parsing", // 'uploading' | 'parsing' | 'vectorizing' | 'completed' | 'error'
    "error_message": null
  }
}
```

#### Final Completed Frame:
```json
{
  "event": "ingestion_progress",
  "data": {
    "filename": "AML_Policy_V2.pdf",
    "progress": 100,
    "status": "completed",
    "error_message": null
  }
}
```

#### Ingestion Error Frame:
```json
{
  "event": "ingestion_progress",
  "data": {
    "filename": "AML_Policy_V2.pdf",
    "progress": 0,
    "status": "error",
    "error_message": "Failed to decode PDF: file corrupted."
  }
}
```

### Backend Implementation Recommendation (FastAPI):
Use FastAPI's `WebSocket` connection manager to broadcast updates during background processing of PDFs.
```python
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try {
        while True:
            # Keep-alive loop
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
During pdf load or ingestion calls, you can run a background task that calls `manager.broadcast` to send real-time percentage reports.

---

## 4. Grounded Answer Generation (RAG QA)

**Status**: ✅ Implemented — `POST /rag/answer` via `AnswerGenerator.generate()`
(`app/api/routes/rag.py`, `app/generation/generator.py`).

Retrieve relevant text chunks from the vector database and generate a grounded, context-aware compliance answer using the local LLM.

* **Endpoint**: `POST /rag/answer`
* **Request Type**: `application/json`
* **Request Schema**: `AnswerRequest`
* **Response Type**: `application/json`
* **Response Schema**: `AnswerResponse`

### `AnswerRequest` JSON Schema:
```json
{
  "query": "What are the suspicious transaction thresholds?",
  "k": 5,
  "doc_type": "policy" // Optional: "policy" | "action" | null
}
```

### `AnswerResponse` JSON Schema:
```json
{
  "answer": "According to the AML policy section 4.2, any transaction exceeding $10,000 USD must be reported [1]. Transactions that appear split to avoid the threshold are also flagged [2].",
  "citations": [
    {
      "id": "1",
      "source": "anti_money_laundering_act.pdf",
      "page": 12,
      "score": 0.895
    },
    {
      "id": "2",
      "source": "suspicious_activity_guidelines.pdf",
      "page": 3,
      "score": 0.841
    }
  ],
  "used_context": true
}
```

---

## 5. System Health Check (`GET /health`)

**Status**: ✅ Implemented — `GET /health` probes both backends and returns
`{status, database, llm}`. DB check via `RagSystem.ping()` (lightweight Chroma `get`);
LLM check via `build_llm_ping()` (HTTP GET `{base_url}/api/tags` on Ollama, 2s timeout).
`status` is `"ok"` when both connected, else `"degraded"`. Probes injected as
dependencies (`get_rag`, `get_llm_ping`) — no Chroma collection or ChatOllama leaked.

To drive the dynamic status badges in the header, the `/health` endpoint should return status reports for both the database and the local LLM generation client (Ollama).

* **Endpoint**: `GET /health`
* **Response Type**: `application/json`
* **Response Schema**:
```json
{
  "status": "ok",
  "database": "connected", // "connected" | "disconnected"
  "llm": "connected"      // "connected" | "disconnected"
}
```

---

## 6. Document Ingestion Text-Cleanup (Feature Request)

**Status**: ✅ Implemented — pure `clean_pdf_text` in
`app/ingestion/rag/cleaning.py` (own module, SRP), applied to each page in `load_pdfs`
before building `Document` models. **Deviation from sketch:** the recommended regex
`[...\x7f-\xff]` was narrowed to `\x7f-\x9f` — the original range deletes the `©` it just
inserted and strips every accented/Latin-1 char (é, ü, £) that real AML docs contain.
Single-break→space uses lookarounds so paragraph gaps (`\n\n`) survive. Unit-tested in
`tests/test_cleaning.py`.

To remove extraction noise, headers/footers, and layout artifacts from uploaded PDFs before creating vector embeddings, the text content extracted from pages must be normalized and cleaned at the load phase.

### Ingestion Cleaning Requirements:
1. **Symbol Normalization**: Replace proprietary or mis-extracted PDF ligatures/glyphs with standard characters (e.g. replace `` with `©`).
2. **Control Character Removal**: Strip non-printable and control characters (e.g., `\x00-\x08`, `\x0b`, `\x0c`, `\x0e-\x1f`, `\x7f-\xff`) that clutter the embeddings vector space.
3. **Hyphenated Line-Join**: Join words that were split across line breaks with a trailing hyphen (e.g., `trans- \n action` -> `transaction`).
4. **Paragraph Spacing Normalization**: Replace single line breaks inside running paragraphs with standard spaces, while preserving actual paragraph gaps (double line breaks `\n\n`).
5. **Whitespace Collapsing**: Collapse multiple consecutive horizontal spaces and tabs into a single space, and strip leading/trailing whitespace.

### Recommended Implementation (loaders.py):
The backend agent should implement a `clean_pdf_text` helper in `backend/app/ingestion/rag/loaders.py` and run it on page content:

```python
import re

def clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    
    # 1. Normalize ligatures & symbols
    text = text.replace("", "©")
    
    # 2. Strip non-printable/control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", "", text)
    
    # 3. Join hyphenated words split by line breaks
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    
    # 4. Join single line breaks inside paragraphs
    text = re.sub(r"([^\n])\n([^\n])", r"\1 \2", text)
    
    # 5. Collapse spaces
    text = re.sub(r"[ \t]+", " ", text)
    
    return text.strip()
```
Apply this utility to `page.page_content` inside `load_pdfs` prior to initializing `Document` models.



