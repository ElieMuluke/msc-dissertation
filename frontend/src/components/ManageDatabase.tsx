import { useState } from "react";
import { clearDatabase } from "../api";

interface ManageDatabaseProps {
  onClearSuccess: () => void;
}

export function ManageDatabase({ onClearSuccess }: ManageDatabaseProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error" | "loading" | null; message: string }>({
    type: null,
    message: "",
  });

  async function onClear() {
    if (!window.confirm("Clear the entire database? This deletes all ingested documents and vector embeddings permanently.")) return;
    setStatus({ type: "loading", message: "Wiping vector indexes…" });
    try {
      await clearDatabase();
      setStatus({ type: "success", message: "Vector store indexes cleared." });
      onClearSuccess();
    } catch (err) {
      setStatus({ type: "error", message: (err as Error).message });
    }
  }

  return (
    <section className="glass-panel rounded-2xl p-6 transition-all duration-300 min-w-0 w-full">
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between cursor-pointer select-none"
      >
        <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
          Database Control
        </h2>
        <svg 
          className={`w-4 h-4 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-355 transform transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`} 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2.5" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {isExpanded && (
        <div className="mt-5 space-y-4 min-w-0 w-full">
        <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
          Wipe the vector database storage. This operation permanently deletes all chunked PDF text and corresponding high-dimensional embeddings.
        </p>

        <button
          type="button"
          onClick={onClear}
          className="w-full py-2.5 px-4 rounded-xl text-sm font-semibold tracking-tight border border-red-200 dark:border-red-900/30 bg-red-50/50 dark:bg-red-950/10 hover:bg-red-500 dark:hover:bg-red-600 text-red-600 dark:text-red-400 hover:text-white dark:hover:text-white transition-all duration-300 active:scale-[0.98]"
        >
          Clear Database Storage
        </button>

        {status.type && (
          <div
            className={`p-3 rounded-xl text-xs flex items-center space-x-2.5 ${
              status.type === "success"
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                : status.type === "error"
                ? "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
                : "bg-neutral-200/50 text-neutral-600 dark:bg-neutral-900/50 dark:text-neutral-400 border border-neutral-200/20"
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              {status.type === "success" ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              )}
            </svg>
            <span>{status.message}</span>
          </div>
        )}
      </div>
      )}
    </section>
  );
}
