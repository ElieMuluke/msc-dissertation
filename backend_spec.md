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


