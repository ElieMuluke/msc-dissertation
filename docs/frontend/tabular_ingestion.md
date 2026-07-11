# Tabular Data Ingestion UI (`UploadTabular.tsx`)

The `UploadTabular` component provides a premium interface for uploading structured financial dataset files (from the IBM/Kaggle "HI-Large" AML dataset) into the SQLite database.

## Features

- **Ingestion Types**: Supports selecting the target ingestion table:
  - `accounts`: Accepts `.csv` files.
  - `transactions`: Accepts `.csv` files.
  - `patterns`: Accepts `.csv` and `.txt` files.
- **Multiple Ingest Methods**:
  - **File Upload**: Drag-and-drop or browse local device files for standard multi-file uploads.
  - **Server Path**: Input a file path on the backend server's disk to directly ingest massive files (e.g. 17GB transaction csv) without HTTP transfer overhead.
  - **Paste CSV**: Paste or type raw CSV text directly into a text area. Validates syntax completely before database insert.
- **Extension Validation**: Dynamically validates staged files based on the selected table's allowed file types and alerts on failure.
- **Volume Display**: Fetches and displays current row counts for `accounts` and `transactions` in real time, updating automatically upon successful uploads.
- **WebSocket Progress Tracking**: Subscribes to the shared WebSocket gateway `/ws` to display a real-time progress bar through the `uploading`, `inserting`, and `completed` phases of ingestion (reused for both HTTP file uploads and server path files).
- **Validation Error Handling**: Categorizes client-side input warnings and handles backend validation responses (422) for raw text pasting, displaying a comprehensive bulleted list of errors to allow in-place corrections.
- **Database Clear Control**: Includes a "Clear Data" capability to wipe all tabular accounts and transactions from SQLite.
- **Status Indicators**: Show custom alerts for success, progress, or detailed backend error messages.

## API Integration

- **Counts Endpoint**: Queries `GET /tabular/counts` on mount and after successful uploads/wipes to update statistics.
- **Ingestion Endpoint**: Performs a `POST /tabular/ingest` using `multipart/form-data` containing the file lists and chosen `data_type`.
- **Local Ingestion Endpoint**: Submits `POST /tabular/ingest/local` containing `{ "data_type": "...", "path": "..." }` for local files.
- **Pasted Ingestion Endpoint**: Submits `POST /tabular/ingest/text` containing `{ "data_type": "...", "csv_text": "..." }` for raw CSV. Returns a `422` with a `detail` array of strings if parsing fails.
- **Clear Endpoint**: Issues a `DELETE /tabular/data` request when the "Clear Data" action is confirmed.

## Prop Interface

This component maintains its own states and requires no external props:
```typescript
export function UploadTabular()
```


