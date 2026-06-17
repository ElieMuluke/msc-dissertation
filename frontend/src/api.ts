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
