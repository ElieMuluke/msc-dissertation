# Streaming Answers (SSE) Integration

This document describes the implementation of Server-Sent Events (SSE) streaming answers in the Compliance Chat workspace.

## Overview
Because generating grounded compliance answers via local LLMs (Ollama) is CPU-intensive and slow, the frontend streams answers token-by-token. This provides immediate visual feedback, matching premium conversational UI designs.

## Implementation Details

### API Layer ([api.ts](file:///home/eliem/projects/ai/dissertation/frontend/src/api.ts))
- **Method**: `POST /rag/answer/stream`
- **Helper**: `streamAnswer(body, handlers, signal)`
- **Response Handling**: Reads SSE response streams chunk-by-chunk using a `ReadableStream` reader and parses individual text/event-stream frames.
- **Citations Mapping**: Resolves source references and maps metadata to pre-fetched vector search hits to attach citation text.
- **Graceful Fallback**: If the server fails to connect, responds with a HTTP error, or yields an LLM `error` frame before returning any tokens, it falls back to a simulated streaming response generated from pre-fetched vector search hits.

### UI Layer ([ChatDocs.tsx](file:///home/eliem/projects/ai/dissertation/frontend/src/components/ChatDocs.tsx))
- Integrated `streamAnswer` in compliance chat workspace.
- Implemented `AbortController` tracking in React refs to cancel active streams if the user clears the chat, submits a new prompt, or unmounts the component.
- Implemented dual-state loading skeleton: displays the bouncing skeleton while waiting for the first token, then transitions instantly to rendering the streaming text block.
