import React, { useState, useRef, useCallback } from "react";
import { uploadPdfs, type DocType } from "../api";
import { useWebSocket } from "../hooks/useWebSocket";

interface UploadDocsProps {
  /** Callback fired after successfully uploading and initiating/completing ingestion. */
  onUploadSuccess: (files: File[], docType: DocType, totalPages: number) => void;
  /** Status of the vector database connection. Ingestion is disabled if disconnected. */
  dbStatus?: "connected" | "disconnected";
}

/**
 * UploadDocs component handles document file selection, drag-and-drop,
 * metadata classification, and uploading documents to the ingestion pipeline.
 * It listens to real-time ingestion progress updates via WebSockets.
 */
export function UploadDocs({ onUploadSuccess, dbStatus }: UploadDocsProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [docType, setDocType] = useState<DocType>("policy");
  const [status, setStatus] = useState<{ type: "success" | "error" | "info" | null; message: string }>({
    type: null,
    message: "",
  });
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeUploadsRef = useRef<Set<string>>(new Set());

  /**
   * WebSocket message handler that processes ingestion progress updates.
   * Updates state with upload progress percentages and success/error notifications.
   */
  const handleWsMessage = useCallback((msg: any) => {
    if (msg.event === "ingestion_progress") {
      const { filename, progress, status: wsStatus, error_message } = msg.data;
      if (activeUploadsRef.current.has(filename)) {
        setUploadProgress(progress);

        if (wsStatus === "completed") {
          setStatus({
            type: "success",
            message: `Ingested "${filename}" successfully.`,
          });
          activeUploadsRef.current.delete(filename);
          if (activeUploadsRef.current.size === 0) {
            setUploadProgress(null);
          }
        } else if (wsStatus === "error") {
          setStatus({
            type: "error",
            message: `Error ingesting "${filename}": ${error_message || "Unknown error"}`,
          });
          activeUploadsRef.current.delete(filename);
          if (activeUploadsRef.current.size === 0) {
            setUploadProgress(null);
          }
        } else {
          const phaseLabel =
            wsStatus === "parsing"
              ? "Parsing PDF pages"
              : wsStatus === "vectorizing"
              ? "Generating vector embeddings"
              : "Uploading document file";

          setStatus({
            type: "info",
            message: `${phaseLabel}... (${filename})`,
          });
        }
      }
    }
  }, []);

  // Listen to WebSocket pushed progress updates
  const { isConnected: isWsConnected } = useWebSocket(handleWsMessage);

  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFiles = Array.from(e.dataTransfer.files).filter(
        (file) => file.type === "application/pdf"
      );
      if (droppedFiles.length > 0) {
        setFiles((prev) => [...prev, ...droppedFiles]);
        setStatus({ type: null, message: "" });
      } else {
        setStatus({ type: "error", message: "Only PDF files are supported." });
      }
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      const selectedFiles = Array.from(e.target.files).filter(
        (file) => file.type === "application/pdf"
      );
      setFiles((prev) => [...prev, ...selectedFiles]);
      setStatus({ type: null, message: "" });
    }
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function clearFiles() {
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;

    // Track filenames for WebSocket updates
    files.forEach((f) => activeUploadsRef.current.add(f.name));

    setStatus({ type: "info", message: `Uploading ${files.length} file(s)…` });
    setUploadProgress(0);

    const uploadedFilesSnapshot = [...files];
    try {
      const ingested = await uploadPdfs(uploadedFilesSnapshot, docType, (percent) => {
        // Fallback progress: only update via XHR if WebSocket is inactive
        if (!isWsConnected) {
          setUploadProgress(percent);
          if (percent === 100) {
            setStatus({ type: "info", message: "Processing embeddings (HTTP fallback)..." });
          }
        }
      });

      // If WebSocket is not connected/supported, resolve local state success triggers
      if (!isWsConnected) {
        setStatus({
          type: "success",
          message: `Ingested ${ingested} pages from ${uploadedFilesSnapshot.length} document(s).`,
        });
        onUploadSuccess(uploadedFilesSnapshot, docType, ingested);
        setUploadProgress(null);
        activeUploadsRef.current.clear();
      } else {
        // If WS is connected, let it handle detailed completions, but sync database lists
        onUploadSuccess(uploadedFilesSnapshot, docType, ingested);
      }

      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setStatus({ type: "error", message: (err as Error).message });
      setUploadProgress(null);
      activeUploadsRef.current.clear();
    }
  }

  return (
    <section className="glass-panel rounded-2xl p-6 transition-all duration-300">
      <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-4">
        Import Documents
      </h2>

      <form onSubmit={onSubmit} className="space-y-5">
        {/* Drag and Drop Zone */}
        <div
          onDragEnter={dbStatus === "disconnected" ? undefined : handleDrag}
          onDragOver={dbStatus === "disconnected" ? undefined : handleDrag}
          onDragLeave={dbStatus === "disconnected" ? undefined : handleDrag}
          onDrop={dbStatus === "disconnected" ? undefined : handleDrop}
          onClick={dbStatus === "disconnected" ? undefined : () => fileInputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 flex flex-col items-center justify-center min-h-[160px] ${
            dbStatus === "disconnected"
              ? "border-rose-300/60 bg-rose-500/5 dark:bg-rose-950/10 cursor-not-allowed"
              : isDragActive
              ? "border-blue-500 bg-blue-500/5 dark:bg-blue-500/10 cursor-pointer"
              : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700 bg-white/40 dark:bg-white/[0.02] cursor-pointer"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            onChange={handleFileChange}
            disabled={dbStatus === "disconnected"}
            className="hidden"
          />

          <svg
            className={`w-10 h-10 mb-3 transition-transform duration-300 ${
              dbStatus === "disconnected"
                ? "text-rose-400 dark:text-rose-600/70"
                : isDragActive
                ? "scale-110 text-blue-500"
                : "text-neutral-400 dark:text-neutral-600"
            }`}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
            />
          </svg>

          <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
            {dbStatus === "disconnected"
              ? "Ingestion Offline"
              : isDragActive
              ? "Drop files here"
              : "Drag & drop PDF files"}
          </p>
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
            {dbStatus === "disconnected"
              ? "Vector Database disconnected"
              : "or click to browse from device"}
          </p>
        </div>

        {/* Selected Files List */}
        {files.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-medium text-neutral-400 dark:text-neutral-500 px-1">
              <span>{files.length} Document(s) Staged</span>
              <button
                type="button"
                onClick={clearFiles}
                className="text-neutral-400 hover:text-red-500 transition-colors"
              >
                Clear all
              </button>
            </div>
            <ul className="max-h-36 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-800/50 border border-neutral-100 dark:border-neutral-800/50 rounded-lg bg-white/30 dark:bg-white/[0.01]">
              {files.map((file, i) => (
                <li key={i} className="flex items-center justify-between p-2.5 text-xs text-neutral-600 dark:text-neutral-400">
                  <div className="flex items-center space-x-2 truncate pr-4">
                    <svg
                      className="w-4 h-4 text-red-500 shrink-0"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                      />
                    </svg>
                    <span className="truncate">{file.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="p-1 rounded-md text-neutral-400 hover:text-red-500 hover:bg-red-500/5 transition-all"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Custom Segmented Control for DocType */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider block">
            Classification / Metadata
          </label>
          <div className="flex p-0.5 rounded-lg bg-neutral-200/60 dark:bg-neutral-800/80">
            <button
              type="button"
              onClick={() => setDocType("policy")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                docType === "policy"
                  ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                  : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
              }`}
            >
              Policy
            </button>
            <button
              type="button"
              onClick={() => setDocType("action")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                docType === "action"
                  ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                  : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
              }`}
            >
              Action
            </button>
          </div>
        </div>

        {/* Submit Action */}
        <button
          type="submit"
          disabled={files.length === 0 || dbStatus === "disconnected"}
          className={`w-full py-2.5 px-4 rounded-xl text-sm font-semibold tracking-tight text-white transition-all duration-300 ${
            files.length === 0 || dbStatus === "disconnected"
              ? "bg-neutral-300 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-600 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/20 active:scale-[0.98]"
          }`}
        >
          {dbStatus === "disconnected"
            ? "Database Disconnected"
            : files.length > 0
            ? `Ingest ${files.length} Document(s)`
            : "Select PDF files"}
        </button>
      </form>

      {/* Upload & Ingestion Progress */}
      {uploadProgress !== null && (
        <div className="space-y-2 mt-4 p-4 rounded-xl border border-neutral-100 dark:border-neutral-800/40 bg-white/50 dark:bg-white/[0.01]">
          <div className="flex justify-between text-xs font-semibold text-neutral-600 dark:text-neutral-400">
            <span className="truncate max-w-[80%]" title={status.message}>
              {status.message || "Ingesting..."}
            </span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-neutral-200 dark:bg-neutral-800 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                uploadProgress === 100
                  ? "bg-emerald-500 animate-pulse"
                  : "bg-blue-600 dark:bg-blue-500"
              }`}
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Styled Status Panel */}
      {status.type && (
        <div
          className={`mt-4 p-4 rounded-xl text-xs flex items-start space-x-2.5 animate-pulse-slow ${
            status.type === "success"
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
              : status.type === "error"
              ? "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
              : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
          }`}
        >
          <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            {status.type === "success" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            )}
            {status.type === "error" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            )}
            {status.type === "info" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            )}
          </svg>
          <span className="leading-normal">{status.message}</span>
        </div>
      )}
    </section>
  );
}
