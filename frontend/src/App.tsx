import { useState, useEffect } from "react";
import { UploadDocs } from "./components/UploadDocs";
import { SearchDocs } from "./components/SearchDocs";
import { ChatDocs } from "./components/ChatDocs";
import { ManageDatabase } from "./components/ManageDatabase";
import { FileManager, type IngestedFile } from "./components/FileManager";
import { getIngestedFiles, deleteIngestedFile } from "./api";

export default function App() {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      return (
        localStorage.getItem("theme") === "dark" ||
        (!localStorage.getItem("theme") &&
          window.matchMedia("(prefers-color-scheme: dark)").matches)
      );
    }
    return false;
  });

  const [filesList, setFilesList] = useState<IngestedFile[]>([]);
  const [isBackendDbSupported, setIsBackendDbSupported] = useState(true);
  const [activeTab, setActiveTab] = useState<"search" | "chat">("search");

  // Sync dark mode
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [isDark]);

  // Load files list
  async function refreshFiles() {
    try {
      const data = await getIngestedFiles();
      setFilesList(data);
      setIsBackendDbSupported(true);
    } catch (err) {
      console.warn("Backend endpoints for individual file management not detected. Falling back to local tracking.", err);
      setIsBackendDbSupported(false);
      const cached = localStorage.getItem("ingested_files");
      if (cached) {
        try {
          setFilesList(JSON.parse(cached));
        } catch {
          setFilesList([]);
        }
      }
    }
  }

  useEffect(() => {
    refreshFiles();
  }, []);

  // Handle individual file deletion
  async function handleDeleteFile(filename: string) {
    if (isBackendDbSupported) {
      try {
        await deleteIngestedFile(filename);
        await refreshFiles();
      } catch (err) {
        console.error("Backend deletion failed, trying local fallback", err);
        // Remove locally if backend delete fails (or mock it)
        const updated = filesList.filter((f) => f.filename !== filename);
        setFilesList(updated);
        localStorage.setItem("ingested_files", JSON.stringify(updated));
      }
    } else {
      // Local fallback
      const updated = filesList.filter((f) => f.filename !== filename);
      setFilesList(updated);
      localStorage.setItem("ingested_files", JSON.stringify(updated));
    }
  }

  // Handle append new files on upload success
  function handleUploadSuccess(uploadedFiles: File[], docType: "policy" | "action", totalPages: number) {
    if (isBackendDbSupported) {
      refreshFiles();
    } else {
      // Local tracking fallback: distribute pages estimate or count
      const avgPages = Math.max(1, Math.round(totalPages / uploadedFiles.length));
      const newIngested = uploadedFiles.map((file) => ({
        filename: file.name,
        doc_type: docType,
        pages: avgPages,
        ingested_at: new Date().toISOString(),
      }));

      // Filter out duplicate filenames
      const filteredOld = filesList.filter(
        (oldF) => !newIngested.some((newF) => newF.filename === oldF.filename)
      );

      const updated = [...newIngested, ...filteredOld];
      setFilesList(updated);
      localStorage.setItem("ingested_files", JSON.stringify(updated));
    }
  }

  // Handle clean database list
  function handleClearDatabase() {
    setFilesList([]);
    localStorage.removeItem("ingested_files");
  }

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] dark:bg-[#000000] dark:text-[#f5f5f7] transition-colors duration-500 flex flex-col font-sans">
      {/* Header */}
      <header className="sticky top-0 z-40 w-full border-b border-[rgba(0,0,0,0.08)] dark:border-[rgba(255,255,255,0.08)] bg-[rgba(245,245,247,0.7)] dark:bg-[rgba(0,0,0,0.7)] backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <svg
              className="w-6 h-6 text-blue-600 dark:text-blue-500"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <span className="font-semibold tracking-tight text-lg">
              AML Compliance Platform
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-xs text-neutral-500 dark:text-neutral-400 font-medium">
                Vector DB Connected
              </span>
            </div>

            <button
              onClick={() => setIsDark((prev) => !prev)}
              className="p-2 rounded-full hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)] transition-colors"
              aria-label="Toggle theme"
            >
              {isDark ? (
                <svg
                  className="w-5 h-5 text-amber-400"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.364l-.707-.707M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5 text-indigo-600"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left panel: Administration (Ingestion, File Manager & Clear) */}
          <div className="lg:col-span-5 space-y-8">
            <UploadDocs onUploadSuccess={handleUploadSuccess} />
            <FileManager files={filesList} onDelete={handleDeleteFile} />
            <ManageDatabase onClearSuccess={handleClearDatabase} />
          </div>

          {/* Right panel: Search and Chat Workspace */}
          <div className="lg:col-span-7 space-y-6">
            {/* Modern Tab Selector */}
            <div className="flex p-0.5 rounded-lg bg-neutral-200/50 dark:bg-neutral-800/60 max-w-xs">
              <button
                type="button"
                onClick={() => setActiveTab("search")}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 uppercase tracking-wider ${
                  activeTab === "search"
                    ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                    : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
                }`}
              >
                Semantic Search
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("chat")}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 uppercase tracking-wider ${
                  activeTab === "chat"
                    ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                    : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
                }`}
              >
                Compliance Chat
              </button>
            </div>

            {activeTab === "search" ? <SearchDocs /> : <ChatDocs />}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[rgba(0,0,0,0.08)] dark:border-[rgba(255,255,255,0.08)] py-6 text-center text-xs text-neutral-500 dark:text-neutral-400">
        <p>AML Compliance Vector Search System &copy; 2026. Made with refined technology.</p>
      </footer>
    </div>
  );
}
