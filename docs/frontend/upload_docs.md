# Upload Documents Component (`UploadDocs.tsx`)

The `UploadDocs` component provides the interface for uploading regulatory policy and financial action PDF documents into the vector database ingestion pipeline.

## Features

- **Drag-and-Drop / File Picker**: Supports drag-and-drop file staging, as well as a native file picker.
- **Validation**: Restricts file selections to PDF files only.
- **Classification Selector**: Allows marking files as either `policy` or `action` metadata classification before uploading.
- **Real-Time Progress Tracking**:
  - Connects to the backend WebSocket endpoint (`/ws/progress`) to receive granular, per-page/per-file ingestion progress.
  - Automatically falls back to standard XHR upload progress monitoring if WebSocket connection is unavailable.
- **Connection Guard**: Disables file selection and ingestion buttons if the vector database is reported as disconnected (`dbStatus === "disconnected"`).

## Design Decisions

### Memoized WebSocket Callback
To prevent continuous WebSocket subscription churn, the message handler callback is memoized:
```typescript
const handleWsMessage = useCallback((msg: any) => {
  // processes events of type "ingestion_progress"
}, []);
```
This ensures that the WebSocket subscription hook (`useWebSocket`) does not tear down and re-establish the connection on every render cycle.

### Fallback Progress Integration
In the absence of a working WebSocket connection, the component falls back to standard HTTP XHR upload progress updates:
```typescript
const ingested = await uploadPdfs(files, docType, (percent) => {
  if (!isWsConnected) {
    setUploadProgress(percent);
  }
});
```

## Prop Interface

```typescript
interface UploadDocsProps {
  /** Callback fired after successfully uploading and initiating/completing ingestion. */
  onUploadSuccess: (files: File[], docType: DocType, totalPages: number) => void;
  /** Status of the vector database connection. Ingestion is disabled if disconnected. */
  dbStatus?: "connected" | "disconnected";
}
```
