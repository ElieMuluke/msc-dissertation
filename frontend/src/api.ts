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

export function uploadPdfs(
  files: File[],
  docType: DocType,
  onProgress?: (percent: number) => void
): Promise<number> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("doc_type", docType);

    if (onProgress && xhr.upload) {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100);
          onProgress(percent);
        }
      });
    }

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve(data.ingested as number);
        } catch {
          reject(new Error("Failed to parse ingestion response"));
        }
      } else {
        reject(
          new Error(
            xhr.responseText || `Upload failed with status ${xhr.status}`
          )
        );
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network upload error"));
    });

    xhr.open("POST", `${API_URL}/rag/documents/pdf`);
    xhr.send(form);
  });
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
    
    return await res.json();
  } catch (error) {
    console.warn("Backend RAG generation (/rag/answer) failed or is unavailable. Using client-side search fallback.", error);
    
    try {
      const searchHits = await search(query, k, docType);
      
      if (searchHits.length === 0) {
        return {
          answer: "I searched the compliance database but found no relevant document sections matching your query. Please ensure your documents are ingested properly and try rephrasing your question.",
          citations: [],
          used_context: false,
        };
      }
      
      const citations: Citation[] = searchHits.map((hit) => ({
        id: hit.id,
        source: String(hit.metadata.source || hit.metadata.filename || "Unknown Source"),
        page: hit.metadata.page ? Number(hit.metadata.page) : undefined,
        score: hit.score,
      }));

      // Generate a structured mock response by presenting findings with sources
      let simulatedAnswer = `Based on the compliance documents retrieved from the vector database, here are the relevant findings:\n\n`;
      
      searchHits.forEach((hit) => {
        // Clean up paragraph text to be concise
        const cleanText = hit.text.replace(/\s+/g, " ").trim();
        const shortText = cleanText.length > 200 ? `${cleanText.substring(0, 197)}...` : cleanText;
        simulatedAnswer += `* **[${hit.id}]** From *${hit.metadata.source || "Document"}* (Page ${hit.metadata.page || "?"}): "${shortText}"\n\n`;
      });
      
      simulatedAnswer += `\n*Note: The local LLM backend is currently unavailable or unconfigured. This response is a structured synthesis of the top retrieved vector search passages.*`;

      return {
        answer: simulatedAnswer,
        citations,
        used_context: true,
      };
    } catch (searchErr) {
      console.error("Vector search fallback also failed:", searchErr);
      throw new Error("Both the RAG generation and search fallback are currently unreachable. Please check if the backend server is running.");
    }
  }
}

