import { useState } from "react";
import { type DocType } from "../api";

export interface IngestedFile {
  filename: string;
  doc_type: DocType;
  pages: number;
  ingested_at: string;
}

interface FileManagerProps {
  files: IngestedFile[];
  onDelete: (filename: string) => Promise<void>;
}

export function FileManager({ files, onDelete }: FileManagerProps) {
  const [filterQuery, setFilterQuery] = useState("");
  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  async function handleDeleteClick(filename: string) {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? This will remove all chunks and embeddings.`)) return;
    setDeletingFile(filename);
    try {
      await onDelete(filename);
    } catch (err) {
      alert(`Error deleting file: ${(err as Error).message}`);
    } finally {
      setDeletingFile(null);
    }
  }

  const filteredFiles = files.filter((f) =>
    f.filename.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <section className="glass-panel rounded-2xl p-6 transition-all duration-300">
      <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-4">
        Ingested Corpus
      </h2>

      <div className="space-y-4">
        {/* Search inside file list */}
        {files.length > 0 && (
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter ingested documents..."
              className="w-full pl-9 pr-3 py-1.5 bg-white/50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-lg text-xs placeholder-neutral-400 focus:outline-none input-minimalist"
            />
          </div>
        )}

        {/* Ingested list */}
        {filteredFiles.length === 0 ? (
          <div className="text-center py-8 text-neutral-400 dark:text-neutral-500">
            <svg
              className="w-8 h-8 mx-auto mb-2 text-neutral-300 dark:text-neutral-700"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
              />
            </svg>
            <p className="text-xs">
              {files.length === 0
                ? "No ingested documents found."
                : "No matching documents found."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-neutral-100 dark:divide-neutral-800/50 max-h-64 overflow-y-auto pr-1">
            {filteredFiles.map((file) => {
              const isPolicy = file.doc_type === "policy";
              const isDeleting = deletingFile === file.filename;
              return (
                <li
                  key={file.filename}
                  className={`flex items-center justify-between py-3.5 first:pt-0 last:pb-0 transition-opacity duration-300 ${
                    isDeleting ? "opacity-50 pointer-events-none" : ""
                  }`}
                >
                  <div className="flex items-start space-x-3 truncate mr-4">
                    {/* PDF Icon */}
                    <div className="p-2 rounded bg-neutral-100 dark:bg-neutral-900 text-red-500 shrink-0">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                        />
                      </svg>
                    </div>

                    <div className="truncate">
                      <p className="text-xs font-semibold text-neutral-800 dark:text-neutral-200 truncate" title={file.filename}>
                        {file.filename}
                      </p>
                      <div className="flex items-center space-x-1.5 mt-1">
                        <span
                          className={`text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.2 rounded ${
                            isPolicy
                              ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                              : "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                          }`}
                        >
                          {file.doc_type}
                        </span>
                        <span className="text-[10px] text-neutral-400 dark:text-neutral-500">
                          {file.pages} {file.pages === 1 ? "page" : "pages"}
                        </span>
                        <span className="text-[10px] text-neutral-300 dark:text-neutral-700">&bull;</span>
                        <span className="text-[10px] text-neutral-400 dark:text-neutral-500">
                          {new Date(file.ingested_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDeleteClick(file.filename)}
                    disabled={isDeleting}
                    className="p-2 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-500/5 transition-all"
                    aria-label={`Delete ${file.filename}`}
                  >
                    {isDeleting ? (
                      <svg className="animate-spin h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
