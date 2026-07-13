# Upload Documents Component (`UploadDocs.tsx`)

The `UploadDocs` component provides the interface for uploading regulatory policy and financial action PDF documents into the vector database ingestion pipeline.

## Features

- **Drag-and-Drop / File Picker**: Supports drag-and-drop file staging, as well as a native file picker.
- **Validation**: Restricts file selections to PDF files only.
- **Real-Time Progress Tracking**: Reads Server-Sent Events (SSE) progress frames (`uploading`, `parsing`, and `vectorizing` phases) directly from the endpoint's response stream to drive the progress indicator.
- **Connection Guard**: Disables file selection and ingestion buttons if the vector database is reported as disconnected (`dbStatus === "disconnected"`).

## Design Decisions

- **SSE Stream Ingestion**: The component calls the updated `uploadPdfs` function, passing an inline `onProgress` callback to handle incoming SSE frames. This avoids the overhead and complexity of a shared global WebSocket subscription.

## Prop Interface

```typescript
interface UploadDocsProps {
  /** Callback fired after successfully uploading and initiating/completing ingestion. */
  onUploadSuccess: (files: File[], totalPages: number) => void;
  /** Status of the vector database connection. Ingestion is disabled if disconnected. */
  dbStatus?: "connected" | "disconnected";
}
```
