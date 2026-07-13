// Typed client for the AML platform backend.
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type DocType = "policy" | "action";

export interface SearchHit {
  id: string;
  text: string;
  doc_type: DocType;
  metadata: Record<string, unknown>;
  score: number;
}

async function readSseProgress(
  res: Response,
  onProgress?: (filename: string, pct: number, status: string) => void
): Promise<number> {
  if (!res.body) throw new Error("Response body is not readable");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let total = 0;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      if (!frame.trim()) continue;
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "progress") {
        onProgress?.(payload.filename, payload.progress, payload.status);
      } else if (event === "error") {
        throw new Error(`${payload.filename}: ${payload.message}`);
      } else if (event === "done") {
        total = payload.ingested;
      }
    }
  }
  return total;
}

export async function uploadPdfs(
  files: File[],
  onProgress?: (filename: string, pct: number, status: string) => void
): Promise<number> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));

  const res = await fetch(`${API_URL}/rag/documents/pdf`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(await res.text() || `Upload failed with status ${res.status}`);
  }

  return readSseProgress(res, onProgress);
}

export async function clearDatabase(): Promise<void> {
  const res = await fetch(`${API_URL}/rag/documents`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

export async function search(q: string, k = 5, docType?: DocType): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q, k: String(k) });
  if (docType) params.set("doc_type", docType);
  const res = await fetch(`${API_URL}/rag/search?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface IngestedFile {
  filename: string;
  doc_type: DocType;
  pages: number;
  ingested_at: string;
}

export async function getIngestedFiles(): Promise<IngestedFile[]> {
  const res = await fetch(`${API_URL}/rag/documents`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteIngestedFile(filename: string): Promise<void> {
  const res = await fetch(
    `${API_URL}/rag/documents/${encodeURIComponent(filename)}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(await res.text());
}

export interface Citation {
  id: string;
  source: string;
  page?: number;
  score: number;
  text?: string;
}

export interface AnswerResponse {
  answer: string;
  citations: Citation[];
  used_context: boolean;
}

export async function askQuestion(
  query: string,
  docType?: DocType,
  k = 5
): Promise<AnswerResponse> {
  // Pre-fetch semantic search hits to resolve citation texts
  let searchHits: SearchHit[] = [];
  try {
    searchHits = await search(query, k, docType);
  } catch (searchErr) {
    console.warn("Failed to pre-fetch search hits for context mapping:", searchErr);
  }

  try {
    const res = await fetch(`${API_URL}/rag/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        k,
        doc_type: docType || null,
      }),
    });
    
    if (!res.ok) {
      throw new Error(`RAG answer failed with status ${res.status}: ${await res.text()}`);
    }
    
    const data = await res.json();
    
    // Attach matching text to backend citations if search hits are available
    const citations: Citation[] = (data.citations || []).map((c: any) => {
      const match = searchHits.find(
        (h) =>
          String(h.metadata.source || h.metadata.filename || "").toLowerCase() === c.source.toLowerCase() &&
          Number(h.metadata.page || 0) === Number(c.page || 0)
      );
      return {
        id: c.id,
        source: c.source,
        page: c.page,
        score: c.score,
        text: match ? cleanPdfNoise(match.text) : undefined,
      };
    });

    return {
      answer: data.answer,
      citations,
      used_context: data.used_context,
    };
  } catch (error) {
    console.warn("Backend RAG generation (/rag/answer) failed or is unavailable. Using client-side search fallback.", error);
    
    if (searchHits.length === 0) {
      return {
        answer: "I searched the compliance database but found no relevant document sections matching your query. Please ensure your documents are ingested properly and try rephrasing your question.",
        citations: [],
        used_context: false,
      };
    }
    
    const citations: Citation[] = searchHits.map((hit, idx) => ({
      id: String(idx + 1),
      source: String(hit.metadata.source || hit.metadata.filename || "Unknown Source"),
      page: hit.metadata.page ? Number(hit.metadata.page) : undefined,
      score: hit.score,
      text: cleanPdfNoise(hit.text),
    }));

    // Generate a structured mock response by presenting concise 200-character findings
    let simulatedAnswer = `Based on the compliance documents retrieved from the vector database, here are the key findings:\n\n`;
    
    searchHits.forEach((hit, idx) => {
      // Clean up paragraph text and PDF noise to be concise
      const cleanText = cleanPdfNoise(hit.text);
      // Truncate to 200 characters inside the main message bubble text as requested
      const shortText = cleanText.length > 200 ? `${cleanText.substring(0, 197)}...` : cleanText;
      const sourceName = hit.metadata.source || "Document";
      const pageInfo = hit.metadata.page !== undefined ? ` (Page ${hit.metadata.page})` : "";
      simulatedAnswer += `- From *${sourceName}*${pageInfo}: "${shortText}" [${idx + 1}]\n\n`;
    });
    
    simulatedAnswer += `*Note: The local LLM backend is currently unavailable or unconfigured. This response is a structured synthesis of the top retrieved vector search passages.*`;

    return {
      answer: simulatedAnswer,
      citations,
      used_context: true,
    };
  }
}

// Clean up repetitive page banners, footers, and other structural PDF noises
export function cleanPdfNoise(text: string): string {
  if (!text) return "";
  return text
    // Remove repeated FATF Recommendations header banners
    .replace(/THE FATF RECOMMENDATIONS\s+INTERNATIONAL STANDARDS\s+ON COMBATING MONEY LAUNDERING\s+AND THE FINANCING OF TERRORISM\s+&\s+PROLIFERATION/gi, "")
    // Remove repeated year ranges
    .replace(/\b2012-202[0-9]\b/g, "")
    // Remove JMLSG headings & section footers
    .replace(/JMLSG\s+Guidance\s+Part\s+I[I]?/gi, "")
    // Collapse spacing and newlines
    .replace(/\s+/g, " ")
    .trim();
}

export interface HealthStatus {
  database: "connected" | "disconnected";
  llm: "connected" | "disconnected";
}

export async function checkSystemHealth(): Promise<HealthStatus> {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) {
      return { database: "disconnected", llm: "disconnected" };
    }
    const data = await res.json();
    return {
      database: data.database || "connected",
      llm: data.llm || "connected",
    };
  } catch (error) {
    return { database: "disconnected", llm: "disconnected" };
  }
}

/**
 * Callback handlers to process streaming SSE events.
 */
export interface StreamHandlers {
  /** Fired repeatedly as new tokens are generated. */
  onToken: (text: string) => void;
  /** Fired repeatedly as thinking process text is generated. */
  onThinking?: (text: string) => void;
  /** Fired once at the end of a successful generation with citations and context flag. */
  onDone: (citations: Citation[], usedContext: boolean) => void;
  /** Fired if request, network, or server generation fails. */
  onError: (message: string) => void;
}

/**
 * Initiates SSE token streaming for RAG compliance answers from /rag/answer/stream.
 * Gracefully falls back to client-side simulated streaming using search hits if backend LLM is offline.
 * 
 * @param body Query parameters including search K limit and doc classification type.
 * @param handlers Handlers to process SSE stream tokens, completion, and error states.
 * @param signal AbortSignal to cancel streaming network request on navigation or context reset.
 */
export async function streamAnswer(
  body: { query: string; k?: number; doc_type?: DocType | null },
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  // Pre-fetch semantic search hits to resolve citation texts
  let searchHits: SearchHit[] = [];
  try {
    searchHits = await search(body.query, body.k ?? 5, body.doc_type || undefined);
  } catch (searchErr) {
    console.warn("Failed to pre-fetch search hits for context mapping:", searchErr);
  }

  let hasReceivedTokens = false;

  const fallback = () => {
    streamFallbackAnswer(searchHits, handlers, signal);
  };

  try {
    const res = await fetch(`${API_URL}/rag/answer/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: body.query,
        k: body.k ?? 5,
        doc_type: body.doc_type || null,
      }),
      signal,
    });

    if (!res.ok || !res.body) {
      console.warn(`Streaming endpoint responded with status ${res.status}. Falling back.`);
      fallback();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a double newline
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? ""; // keep the trailing partial frame

      for (const frame of frames) {
        if (!frame.trim()) continue;
        let event = "message";
        let data = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const payload = JSON.parse(data);

        if (event === "token") {
          hasReceivedTokens = true;
          handlers.onToken(payload.text);
        } else if (event === "thinking") {
          handlers.onThinking?.(payload.text);
        } else if (event === "done") {
          // Map citations to search hits for resolved text
          const citations: Citation[] = (payload.citations || []).map((c: any) => {
            const match = searchHits.find(
              (h) =>
                String(h.metadata.source || h.metadata.filename || "").toLowerCase() === c.source.toLowerCase() &&
                Number(h.metadata.page || 0) === Number(c.page || 0)
            );
            return {
              id: c.id,
              source: c.source,
              page: c.page,
              score: c.score,
              text: match ? cleanPdfNoise(match.text) : undefined,
            };
          });
          handlers.onDone(citations, payload.used_context);
        } else if (event === "error") {
          if (!hasReceivedTokens) {
            console.warn("Stream error before tokens. Falling back.", payload.message);
            fallback();
          } else {
            handlers.onError(payload.message);
          }
          return;
        }
      }
    }
  } catch (error) {
    if (signal?.aborted) return;
    console.warn("Streaming fetch error. Falling back.", error);
    fallback();
  }
}

function streamFallbackAnswer(
  searchHits: SearchHit[],
  handlers: StreamHandlers,
  signal?: AbortSignal
) {
  if (searchHits.length === 0) {
    handlers.onDone([], false);
    handlers.onError("I searched the compliance database but found no relevant document sections matching your query. Please ensure your documents are ingested properly and try rephrasing your question.");
    return;
  }

  const citations: Citation[] = searchHits.map((hit, idx) => ({
    id: String(idx + 1),
    source: String(hit.metadata.source || hit.metadata.filename || "Unknown Source"),
    page: hit.metadata.page ? Number(hit.metadata.page) : undefined,
    score: hit.score,
    text: cleanPdfNoise(hit.text),
  }));

  let simulatedAnswer = `Based on the compliance documents retrieved from the vector database, here are the key findings:\n\n`;
  
  searchHits.forEach((hit, idx) => {
    const cleanText = cleanPdfNoise(hit.text);
    const shortText = cleanText.length > 200 ? `${cleanText.substring(0, 197)}...` : cleanText;
    const sourceName = hit.metadata.source || "Document";
    const pageInfo = hit.metadata.page !== undefined ? ` (Page ${hit.metadata.page})` : "";
    simulatedAnswer += `- From *${sourceName}*${pageInfo}: "${shortText}" [${idx + 1}]\n\n`;
  });
  
  simulatedAnswer += `*Note: The local LLM backend is currently unavailable or unconfigured. This response is a structured synthesis of the top retrieved vector search passages.*`;

  const tokens = simulatedAnswer.split(/(\s+)/);
  let index = 0;

  const interval = setInterval(() => {
    if (signal?.aborted) {
      clearInterval(interval);
      return;
    }
    if (index < tokens.length) {
      handlers.onToken(tokens[index]);
      index++;
    } else {
      clearInterval(interval);
      handlers.onDone(citations, true);
    }
  }, 25);
}


export interface TabularCounts {
  accounts: number;
  transactions: number;
}

export class ValidationError extends Error {
  details: string[];
  constructor(details: string[]) {
    super(details.join("\n"));
    this.name = "ValidationError";
    this.details = details;
  }
}

export async function ingestTabular(
  dataType: "accounts" | "transactions" | "patterns",
  files: File[],
  onProgress?: (filename: string, pct: number, status: string) => void
): Promise<number> {
  const form = new FormData();
  form.append("data_type", dataType);
  files.forEach((file) => form.append("files", file));

  const res = await fetch(`${API_URL}/tabular/ingest`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(await res.text() || `Ingestion failed with status ${res.status}`);
  }

  return readSseProgress(res, onProgress);
}

export async function ingestTabularLocal(
  dataType: "accounts" | "transactions" | "patterns",
  path: string,
  onProgress?: (filename: string, pct: number, status: string) => void
): Promise<number> {
  const res = await fetch(`${API_URL}/tabular/ingest/local`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data_type: dataType, path }),
  });

  if (!res.ok) {
    throw new Error(await res.text() || `Local ingestion failed with status ${res.status}`);
  }

  return readSseProgress(res, onProgress);
}

export async function ingestTabularText(
  dataType: "accounts" | "transactions" | "patterns",
  csvText: string
): Promise<number> {
  const res = await fetch(`${API_URL}/tabular/ingest/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data_type: dataType, csv_text: csvText }),
  });

  if (res.status === 422) {
    try {
      const errData = await res.json();
      if (errData && Array.isArray(errData.detail)) {
        throw new ValidationError(errData.detail);
      }
    } catch (e) {
      if (e instanceof ValidationError) throw e;
    }
    throw new Error("Validation failed on pasted text");
  }

  if (!res.ok) {
    throw new Error(await res.text() || `Ingestion failed with status ${res.status}`);
  }

  const data = await res.json();
  return data.ingested as number;
}

export async function getTabularCounts(): Promise<TabularCounts> {
  const res = await fetch(`${API_URL}/tabular/counts`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clearTabularData(): Promise<void> {
  const res = await fetch(`${API_URL}/tabular/data`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}



