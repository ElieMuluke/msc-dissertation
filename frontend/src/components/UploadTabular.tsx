import React, { useState, useEffect, useRef } from "react";
import {
  ingestTabular,
  ingestTabularLocal,
  ingestTabularText,
  getTabularCounts,
  clearTabularData,
  ValidationError,
  type TabularCounts,
} from "../api";

export function UploadTabular() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [dataType, setDataType] = useState<"accounts" | "transactions" | "patterns">("accounts");
  const [ingestMethod, setIngestMethod] = useState<"file" | "path" | "text">("file");
  const [files, setFiles] = useState<File[]>([]);
  const [serverPath, setServerPath] = useState("");
  const [csvText, setCsvText] = useState("");
  const [counts, setCounts] = useState<TabularCounts | null>(null);
  const [countsError, setCountsError] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [status, setStatus] = useState<{
    type: "success" | "error" | "info" | null;
    message: string;
    validationErrors?: string[];
  }>({
    type: null,
    message: "",
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load counts on mount
  async function fetchCounts() {
    setCountsError(false);
    try {
      const data = await getTabularCounts();
      setCounts(data);
    } catch (err) {
      console.warn("Failed to fetch tabular counts", err);
      setCountsError(true);
    }
  }

  useEffect(() => {
    fetchCounts();
  }, []);

  const allowedExtensions = dataType === "patterns" ? [".csv", ".txt"] : [".csv"];

  function validateFiles(selectedFiles: File[]): File[] {
    return selectedFiles.filter((file) => {
      const name = file.name.toLowerCase();
      return allowedExtensions.some((ext) => name.endsWith(ext));
    });
  }

  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  }

  // Handle drops
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      const valid = validateFiles(droppedFiles);
      if (valid.length > 0) {
        setFiles((prev) => [...prev, ...valid]);
        setStatus({ type: null, message: "" });
      } else {
        setStatus({
          type: "error",
          message: `Only ${allowedExtensions.join(" or ")} files are supported for ${dataType}.`,
        });
      }
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      const selectedFiles = Array.from(e.target.files);
      const valid = validateFiles(selectedFiles);
      if (valid.length > 0) {
        setFiles((prev) => [...prev, ...valid]);
        setStatus({ type: null, message: "" });
      } else {
        setStatus({
          type: "error",
          message: `Only ${allowedExtensions.join(" or ")} files are supported for ${dataType}.`,
        });
      }
    }
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function clearFiles() {
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // Clear staged files and inputs when data type or method changes
  useEffect(() => {
    clearFiles();
    setServerPath("");
    setCsvText("");
    setStatus({ type: null, message: "" });
  }, [dataType, ingestMethod]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (ingesting) return;

    if (ingestMethod === "file") {
      if (files.length === 0) return;

      setIngesting(true);
      setStatus({ type: "info", message: `Uploading ${files.length} file(s)…` });
      setUploadProgress(0);

      const uploadedFilesSnapshot = [...files];

      try {
        const rowsIngested = await ingestTabular(
          dataType,
          uploadedFilesSnapshot,
          (filename, progress, currentStatus) => {
            setUploadProgress(progress);
            const phaseLabel =
              currentStatus === "inserting"
                ? "Inserting records into DB"
                : currentStatus === "uploading"
                ? "Uploading tabular file"
                : "Processing tabular data";

            setStatus({
              type: "info",
              message: `${phaseLabel}... (${filename})`,
            });
          }
        );

        setStatus({
          type: "success",
          message: `Successfully ingested ${rowsIngested.toLocaleString()} rows into ${dataType}.`,
        });
        setUploadProgress(null);
        clearFiles();
        await fetchCounts();
      } catch (err) {
        setStatus({
          type: "error",
          message: (err as Error).message || "An ingestion error occurred.",
        });
        setUploadProgress(null);
      } finally {
        setIngesting(false);
      }
    } else if (ingestMethod === "path") {
      if (!serverPath.trim()) return;

      const basename = serverPath.split(/[/\\]/).pop() || "local-file";

      setIngesting(true);
      setStatus({ type: "info", message: `Initiating ingestion from server path: ${basename}...` });
      setUploadProgress(0);

      try {
        const rowsIngested = await ingestTabularLocal(
          dataType,
          serverPath.trim(),
          (filename, progress, currentStatus) => {
            setUploadProgress(progress);
            const phaseLabel =
              currentStatus === "inserting"
                ? "Inserting records into DB"
                : currentStatus === "uploading"
                ? "Uploading tabular file"
                : "Processing tabular data";

            setStatus({
              type: "info",
              message: `${phaseLabel}... (${filename})`,
            });
          }
        );

        setStatus({
          type: "success",
          message: `Successfully ingested ${rowsIngested.toLocaleString()} rows from local path.`,
        });
        setUploadProgress(null);
        setServerPath("");
        await fetchCounts();
      } catch (err) {
        setStatus({
          type: "error",
          message: (err as Error).message || "An ingestion error occurred.",
        });
        setUploadProgress(null);
      } finally {
        setIngesting(false);
      }
    } else if (ingestMethod === "text") {
      if (!csvText.trim()) return;

      setIngesting(true);
      setStatus({ type: "info", message: "Validating and ingesting CSV text..." });

      try {
        const rowsIngested = await ingestTabularText(dataType, csvText);
        setStatus({
          type: "success",
          message: `Successfully ingested ${rowsIngested.toLocaleString()} rows from text.`,
        });
        setCsvText("");
        await fetchCounts();
      } catch (err) {
        if (err instanceof ValidationError) {
          setStatus({
            type: "error",
            message: "CSV Validation failed:",
            validationErrors: err.details,
          });
        } else {
          setStatus({
            type: "error",
            message: (err as Error).message || "An ingestion error occurred.",
          });
        }
      } finally {
        setIngesting(false);
      }
    }
  }

  async function onClearTabular() {
    if (!window.confirm("Clear all ingested tabular data? This permanently deletes all accounts and transactions.")) return;
    setIngesting(true);
    setStatus({ type: "info", message: "Clearing tabular data..." });
    try {
      await clearTabularData();
      setStatus({ type: "success", message: "Tabular data cleared." });
      await fetchCounts();
    } catch (err) {
      setStatus({ type: "error", message: (err as Error).message });
    } finally {
      setIngesting(false);
    }
  }

  return (
    <section className="glass-panel rounded-2xl p-6 transition-all duration-300 min-w-0 w-full">
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between cursor-pointer select-none"
      >
        <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
          Import Tabular Data
        </h2>
        <div className="flex items-center space-x-3" onClick={(e) => e.stopPropagation()}>
          {counts && (counts.accounts > 0 || counts.transactions > 0) && (
            <button
              type="button"
              onClick={onClearTabular}
              disabled={ingesting}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-500 text-red-600 dark:text-red-400 hover:text-white dark:hover:text-white transition-all duration-300 text-[10px] font-bold uppercase tracking-wider disabled:opacity-50 active:scale-[0.96]"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              <span>Clear</span>
            </button>
          )}
          <svg 
            className={`w-4 h-4 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-350 transform transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`} 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2.5" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-5 space-y-5 min-w-0 w-full">

      {/* Volume Display Stats */}
      <div className="grid grid-cols-2 gap-3.5">
        {countsError ? (
          <div className="col-span-2 relative overflow-hidden bg-red-500/10 dark:bg-red-950/20 border border-red-500/20 dark:border-red-900/30 rounded-xl p-3.5 flex items-center justify-between transition-all duration-300">
            <div className="flex items-center space-x-2.5 text-red-600 dark:text-red-400">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-xs font-bold uppercase tracking-wide">
                Couldn't load database counts
              </span>
            </div>
            <button
              type="button"
              onClick={fetchCounts}
              className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500 text-red-700 dark:text-red-300 hover:text-white dark:hover:text-white transition-all duration-300 text-[10px] font-bold uppercase tracking-wider active:scale-95 shadow-sm"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            <div className="relative overflow-hidden bg-white/40 dark:bg-neutral-900/20 border border-neutral-100 dark:border-neutral-800/50 rounded-xl p-3.5 flex flex-col transition-all duration-300 hover:border-blue-500/30 hover:bg-blue-500/[0.01] hover:shadow-[0_2px_8px_rgba(59,130,246,0.04)] group">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
                  Accounts
                </span>
                <svg className="w-4 h-4 text-neutral-400/70 group-hover:text-blue-500/70 transition-colors duration-300" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <span className="text-xl font-extrabold mt-1.5 text-neutral-850 dark:text-neutral-100 tracking-tight">
                {counts ? counts.accounts.toLocaleString() : "0"}
              </span>
            </div>
            <div className="relative overflow-hidden bg-white/40 dark:bg-neutral-900/20 border border-neutral-100 dark:border-neutral-800/50 rounded-xl p-3.5 flex flex-col transition-all duration-300 hover:border-indigo-500/30 hover:bg-indigo-500/[0.01] hover:shadow-[0_2px_8px_rgba(99,102,241,0.04)] group">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
                  Transactions
                </span>
                <svg className="w-4 h-4 text-neutral-400/70 group-hover:text-indigo-500/70 transition-colors duration-300" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
              </div>
              <span className="text-xl font-extrabold mt-1.5 text-neutral-850 dark:text-neutral-100 tracking-tight">
                {counts ? counts.transactions.toLocaleString() : "0"}
              </span>
            </div>
          </>
        )}
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        {/* Data Type Selection */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider block">
            Dataset Table
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(["accounts", "transactions", "patterns"] as const).map((type) => {
              const isActive = dataType === type;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setDataType(type)}
                  disabled={ingesting}
                  className={`flex flex-col items-center justify-center p-2.5 rounded-xl border text-center transition-all duration-200 active:scale-[0.97] group disabled:opacity-50 ${
                    isActive
                      ? "border-blue-500 bg-blue-500/[0.03] dark:bg-blue-500/[0.06] shadow-[0_2px_8px_rgba(59,130,246,0.08)]"
                      : "border-neutral-200 dark:border-neutral-800/60 bg-white/30 dark:bg-white/[0.01] hover:border-neutral-350 dark:hover:border-neutral-750 hover:bg-neutral-50/20 dark:hover:bg-neutral-900/10"
                  }`}
                >
                  {type === "accounts" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  )}
                  {type === "transactions" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                    </svg>
                  )}
                  {type === "patterns" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  )}
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${isActive ? "text-blue-600 dark:text-blue-400" : "text-neutral-500 dark:text-neutral-400"}`}>
                    {type}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Ingest Method Selection */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider block">
            Ingest Method
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(["file", "path", "text"] as const).map((method) => {
              const isActive = ingestMethod === method;
              return (
                <button
                  key={method}
                  type="button"
                  onClick={() => setIngestMethod(method)}
                  disabled={ingesting}
                  className={`flex flex-col items-center justify-center p-2.5 rounded-xl border text-center transition-all duration-200 active:scale-[0.97] group disabled:opacity-50 ${
                    isActive
                      ? "border-blue-500 bg-blue-500/[0.03] dark:bg-blue-500/[0.06] shadow-[0_2px_8px_rgba(59,130,246,0.08)]"
                      : "border-neutral-200 dark:border-neutral-800/60 bg-white/30 dark:bg-white/[0.01] hover:border-neutral-350 dark:hover:border-neutral-750 hover:bg-neutral-50/20 dark:hover:bg-neutral-900/10"
                  }`}
                >
                  {method === "file" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                  )}
                  {method === "path" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  )}
                  {method === "text" && (
                    <svg className={`w-4 h-4 mb-1.5 transition-colors duration-200 ${isActive ? "text-blue-500" : "text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  )}
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${isActive ? "text-blue-600 dark:text-blue-400" : "text-neutral-500 dark:text-neutral-400"}`}>
                    {method === "file" ? "Upload" : method === "path" ? "Path" : "Paste"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Dynamic Ingestion Method Fields */}
        {ingestMethod === "file" && (
          <>
            {/* Drag and Drop Zone */}
            <div
              onDragEnter={ingesting ? undefined : handleDrag}
              onDragOver={ingesting ? undefined : handleDrag}
              onDragLeave={ingesting ? undefined : handleDrag}
              onDrop={ingesting ? undefined : handleDrop}
              onClick={ingesting ? undefined : () => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-2xl p-6 text-center transition-all duration-300 flex flex-col items-center justify-center min-h-[140px] group ${
                ingesting
                  ? "border-neutral-200 bg-neutral-100/50 dark:bg-neutral-900/10 cursor-not-allowed"
                  : isDragActive
                  ? "border-blue-500 bg-blue-500/5 dark:bg-blue-500/10 cursor-pointer shadow-[0_4px_20px_rgba(59,130,246,0.08)]"
                  : "border-neutral-200 dark:border-neutral-850 hover:border-blue-500/40 hover:bg-neutral-50/30 dark:hover:bg-neutral-900/10 bg-white/40 dark:bg-white/[0.02] cursor-pointer"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={allowedExtensions.join(",")}
                multiple
                onChange={handleFileChange}
                disabled={ingesting}
                className="hidden"
              />

              <div className="p-3 rounded-2xl bg-neutral-100/60 dark:bg-neutral-900/50 text-neutral-400 group-hover:text-blue-500 group-hover:scale-110 group-hover:bg-blue-500/5 transition-all duration-300 mb-2.5">
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
                  />
                </svg>
              </div>

              <p className="text-xs font-bold text-neutral-800 dark:text-neutral-200 group-hover:text-neutral-900 dark:group-hover:text-white transition-colors duration-200">
                {isDragActive ? "Drop tabular files here" : `Drag & drop ${allowedExtensions.join("/")}`}
              </p>
              <p className="text-[10px] text-neutral-400 dark:text-neutral-500 mt-1">
                or click to browse from device
              </p>
            </div>

            {/* Selected Files list */}
            {files.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[10px] font-semibold text-neutral-400 dark:text-neutral-500 px-1">
                  <span>{files.length} File(s) Staged</span>
                  <button
                    type="button"
                    onClick={clearFiles}
                    disabled={ingesting}
                    className="text-neutral-400 hover:text-red-500 transition-colors disabled:opacity-50"
                  >
                    Clear all
                  </button>
                </div>
                <ul className="max-h-28 overflow-y-auto divide-y divide-neutral-100 dark:divide-neutral-800/50 border border-neutral-100 dark:border-neutral-800/50 rounded-lg bg-white/30 dark:bg-white/[0.01]">
                  {files.map((file, i) => (
                    <li key={i} className="flex items-center justify-between py-2 px-2.5 hover:bg-neutral-50/50 dark:hover:bg-neutral-900/40 transition-colors text-[10px] text-neutral-600 dark:text-neutral-400">
                      <div className="flex items-center space-x-2 truncate pr-4">
                        <svg
                          className="w-3.5 h-3.5 text-emerald-500 shrink-0"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                        <span className="truncate font-semibold">{file.name}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(i)}
                        disabled={ingesting}
                        className="p-1 rounded-md text-neutral-450 hover:text-red-500 hover:bg-red-500/5 transition-all disabled:opacity-50"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        {ingestMethod === "path" && (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider block">
              Server File Path
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-neutral-400 dark:text-neutral-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </span>
              <input
                type="text"
                value={serverPath}
                onChange={(e) => setServerPath(e.target.value)}
                disabled={ingesting}
                placeholder="/absolute/path/on/server/file.csv"
                className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/40 dark:bg-white/[0.02] focus:outline-none focus:border-blue-500/50 focus:shadow-[0_0_12px_rgba(59,130,246,0.06)] text-neutral-850 dark:text-neutral-100 transition-all duration-300"
              />
            </div>
            <p className="text-[10px] text-neutral-450 dark:text-neutral-500 leading-relaxed">
              Provide the absolute path to a {allowedExtensions.join("/")} file on the backend server's filesystem.
            </p>
          </div>
        )}

        {ingestMethod === "text" && (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider block">
              CSV Text Content
            </label>
            <textarea
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              disabled={ingesting}
              rows={6}
              placeholder={
                dataType === "patterns"
                  ? "Bank A Name,Bank A ID,Bank B Name,Bank B ID,..."
                  : "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\nBank A,001,111,E1,Alice\n"
              }
              className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/40 dark:bg-white/[0.02] focus:outline-none focus:border-blue-500/50 focus:shadow-[0_0_12px_rgba(59,130,246,0.06)] text-neutral-850 dark:text-neutral-100 transition-all duration-300"
            />
            <p className="text-[10px] text-neutral-450 dark:text-neutral-500 leading-relaxed">
              Type or paste raw CSV rows. A header row is required for {dataType === "patterns" ? "patterns" : "accounts and transactions"}.
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={
            ingesting ||
            (ingestMethod === "file" && files.length === 0) ||
            (ingestMethod === "path" && !serverPath.trim()) ||
            (ingestMethod === "text" && !csvText.trim())
          }
          className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold tracking-tight text-white transition-all duration-300 active:scale-[0.98] ${
            ingesting ||
            (ingestMethod === "file" && files.length === 0) ||
            (ingestMethod === "path" && !serverPath.trim()) ||
            (ingestMethod === "text" && !csvText.trim())
              ? "bg-neutral-200 dark:bg-neutral-850/50 text-neutral-400 dark:text-neutral-600 cursor-not-allowed border border-neutral-300/5 dark:border-neutral-800/10"
              : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 hover:shadow-lg hover:shadow-blue-500/20"
          }`}
        >
          {ingesting ? (
            <span className="flex items-center justify-center space-x-1.5">
              <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Ingesting Tabular Data...</span>
            </span>
          ) : ingestMethod === "file" ? (
            files.length > 0 ? `Ingest ${files.length} File(s)` : "Select Tabular Files"
          ) : ingestMethod === "path" ? (
            serverPath.trim() ? "Ingest from Server Path" : "Enter Server Path"
          ) : (
            csvText.trim() ? "Ingest CSV Text" : "Paste CSV Text"
          )}
        </button>
      </form>

      {/* Upload & Ingestion Progress */}
      {uploadProgress !== null && (
        <div className="space-y-2 mt-4 p-4 rounded-xl border border-neutral-100 dark:border-neutral-800/40 bg-white/50 dark:bg-white/[0.01]">
          <div className="flex justify-between text-[11px] font-semibold text-neutral-600 dark:text-neutral-400">
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

      {/* Styled Status Alert */}
      {status.type && (
        <div
          className={`p-3.5 rounded-xl text-[11px] flex flex-col space-y-2 border ${
            status.type === "success"
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-455 border-emerald-500/20"
              : status.type === "error"
              ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
              : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
          }`}
        >
          <div className="flex items-start space-x-2.5">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              {status.type === "success" ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              ) : status.type === "error" ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              )}
            </svg>
            <span className="leading-normal font-semibold">{status.message}</span>
          </div>
          {status.type === "error" && status.validationErrors && status.validationErrors.length > 0 && (
            <ul className="list-disc list-inside pl-6 space-y-1 text-red-500 dark:text-red-400 leading-normal max-h-40 overflow-y-auto">
              {status.validationErrors.map((err, idx) => (
                <li key={idx} className="text-[10px] font-mono whitespace-pre-wrap">{err}</li>
              ))}
            </ul>
          )}
        </div>
      )}
        </div>
      )}
    </section>
  );
}
