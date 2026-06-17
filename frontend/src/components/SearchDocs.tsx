import { useState } from "react";
import { search, type DocType, type SearchHit } from "../api";

// Clean up spacing, line breaks, and hyphens resulting from PDF extraction
function cleanPdfExtractionText(text: string): string {
  return text
    // Join words cut off with a hyphen at the end of a line (e.g. trans- \n action)
    .replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2")
    // Replace single line breaks inside sentences with standard spaces
    .replace(/([^\n])\n([^\n])/g, "$1 $2")
    // Collapse multiple horizontal spaces/tabs
    .replace(/[ \t]+/g, " ")
    .trim();
}

// Regex-based token highlighter for query keywords, monetary figures, regulations, and section tags
function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!text) return null;

  const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
  const words = escapedQuery.split(/\s+/).filter((w) => w.length > 2);
  const sortedQueryTerms = [...new Set(words)].sort((a, b) => b.length - a.length);

  const fullQueryPattern = escapedQuery.trim() ? `\\b${escapedQuery.trim()}\\b` : "";
  const wordsPattern = sortedQueryTerms.length > 0 ? `\\b(?:${sortedQueryTerms.join("|")})\\b` : "";
  const thresholdPattern = `\\$\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?|\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?\\s*(?:USD|EUR|GBP|dollars|euros|cents)\\b`;
  const regulationPattern = `\\b(?:USA PATRIOT Act|Bank Secrecy Act|FinCEN|FATF|OFAC|BSA|AML\\/CFT|SEC|FCA|compliance)\\b`;
  const sectionPattern = `\\b(?:Section|Sec\\.|Article|Art\\.|Part)\\s+\\d+[A-Za-z0-9\\.\\-]*\\b`;

  const regexParts = [
    fullQueryPattern,
    wordsPattern,
    thresholdPattern,
    regulationPattern,
    sectionPattern
  ].filter(Boolean);

  if (regexParts.length === 0) return <>{text}</>;

  const combinedRegex = new RegExp(`(${regexParts.join("|")})`, "gi");
  const parts = text.split(combinedRegex);

  return (
    <>
      {parts.map((part, i) => {
        if (!part) return null;
        
        const isMatch = combinedRegex.test(part);
        if (!isMatch) return part;

        // Verify matches for specific syntax types
        if (fullQueryPattern && new RegExp(`^${fullQueryPattern}$`, "i").test(part)) {
          return (
            <mark
              key={i}
              className="bg-amber-500/25 text-amber-950 border-b border-amber-500/40 dark:bg-amber-500/35 dark:text-amber-200 px-0.5 rounded-sm font-semibold"
            >
              {part}
            </mark>
          );
        }

        if (wordsPattern && new RegExp(`^${wordsPattern}$`, "i").test(part)) {
          return (
            <mark
              key={i}
              className="bg-blue-500/10 text-blue-800 dark:bg-blue-500/20 dark:text-blue-200 px-0.5 rounded-sm font-medium"
            >
              {part}
            </mark>
          );
        }

        if (new RegExp(`^(${thresholdPattern})$`, "i").test(part)) {
          return (
            <span
              key={i}
              className="font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/5 px-1 rounded border border-emerald-500/10 dark:border-emerald-500/20 tracking-tight"
            >
              {part}
            </span>
          );
        }

        if (new RegExp(`^(${regulationPattern})$`, "i").test(part)) {
          return (
            <span
              key={i}
              className="font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-500/5 dark:bg-indigo-500/10 px-1.5 py-0.2 rounded border border-indigo-500/10 dark:border-indigo-500/20"
            >
              {part}
            </span>
          );
        }

        if (new RegExp(`^(${sectionPattern})$`, "i").test(part)) {
          return (
            <span
              key={i}
              className="font-semibold text-neutral-800 dark:text-neutral-200 font-mono text-[10px] tracking-tight bg-neutral-100 dark:bg-neutral-900 px-1 py-0.5 rounded border border-neutral-200/50 dark:border-neutral-800/80"
            >
              {part}
            </span>
          );
        }

        return part;
      })}
    </>
  );
}

// Helper component to format retrieved text with paragraph, list, and section breaks
function FormattedRetrievedText({ text, query }: { text: string; query: string }) {
  // 1. Clean spacing issues resulting from PDF extract
  const cleanedText = cleanPdfExtractionText(text);

  // 2. Identify paragraphs by double newline splits
  const paragraphs = cleanedText.split(/\n\s*\n/).filter(Boolean);

  return (
    <div className="space-y-3.5 bg-neutral-50/50 dark:bg-neutral-900/10 border border-neutral-100 dark:border-neutral-900/60 rounded-xl p-4 shadow-inner">
      {paragraphs.map((para, pIdx) => {
        // Detect bulleted lists (•, -, *, or numbered lists)
        const listRegex = /^([•\-\*]|\d+\.)\s+(.*)/;
        const listMatch = para.match(listRegex);

        // Detect regulatory/governance section headers
        const sectionRegex = /^(section|article|part|clause|sub-clause|paragraph)\s+\d+[\w\d\.\-]*|^[A-Z\s]{4,30}$/i;
        const isSection = sectionRegex.test(para);

        if (listMatch) {
          const content = listMatch[2];
          return (
            <div key={pIdx} className="flex items-start space-x-2 pl-2">
              <span className="text-blue-500 dark:text-blue-400 mt-1.5 shrink-0 text-[10px]">&bull;</span>
              <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400 font-normal">
                <HighlightedText text={content} query={query} />
              </p>
            </div>
          );
        }

        if (isSection) {
          return (
            <h4
              key={pIdx}
              className="text-xs font-bold uppercase tracking-wider text-neutral-800 dark:text-neutral-200 mt-4 pt-1.5 border-t border-neutral-200/30 dark:border-neutral-800/30 first:mt-0 first:pt-0 first:border-0"
            >
              <HighlightedText text={para} query={query} />
            </h4>
          );
        }

        return (
          <p key={pIdx} className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-400 font-normal">
            <HighlightedText text={para} query={query} />
          </p>
        );
      })}
    </div>
  );
}

// Individual Search Result Card Component with localized copy state
function SearchHitCard({ hit, query }: { hit: SearchHit; query: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(hit.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Clipboard copy failed", err);
    }
  }

  const isPolicy = hit.doc_type === "policy";
  
  // Extract key reference values
  const sourceFile = String(hit.metadata.source || hit.metadata.filename || "Unknown Source");
  const page = String(hit.metadata.page || hit.metadata.page_number || hit.metadata.pg || "");

  // Filter out redundant values from the secondary metadata tags list
  const filterKeys = ["source", "filename", "page", "page_number", "pg", "doc_type"];
  const extraMetadata = Object.entries(hit.metadata).filter(
    ([key]) => !filterKeys.includes(key.toLowerCase())
  );

  // Format relevance match score
  const matchPercent = hit.score >= 0 && hit.score <= 1 
    ? (hit.score * 100).toFixed(1) 
    : null;

  return (
    <article
      className={`glass-panel rounded-2xl p-5 border-l-4 transition-all duration-300 hover:shadow-md ${
        isPolicy ? "border-l-blue-500" : "border-l-indigo-500"
      }`}
    >
      {/* Top Source Reference Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-100 dark:border-neutral-800/40 pb-3 mb-3.5">
        <div className="flex items-center space-x-2 text-xs font-semibold text-neutral-500 dark:text-neutral-400">
          <svg className="w-4 h-4 text-red-500 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
          <span className="truncate max-w-[200px]" title={sourceFile}>
            {sourceFile}
          </span>
          {page && (
            <>
              <span className="text-neutral-300 dark:text-neutral-700">&bull;</span>
              <span className="bg-neutral-100 dark:bg-neutral-900 px-2 py-0.5 rounded text-[10px] text-neutral-600 dark:text-neutral-400">
                Page {page}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* Classification type */}
          <span
            className={`text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
              isPolicy
                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                : "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
            }`}
          >
            {hit.doc_type}
          </span>

          {/* Relevance Meter */}
          {matchPercent ? (
            <span className="inline-flex items-center space-x-1.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
              <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
              <span>{matchPercent}% Match</span>
            </span>
          ) : (
            <span className="text-xs font-semibold text-neutral-400">
              Score: {hit.score.toFixed(3)}
            </span>
          )}
        </div>
      </div>

      {/* Main Chunk Body Text */}
      <FormattedRetrievedText text={hit.text} query={query} />

      {/* Footer Details: Extra Metadata Tags & Interactive Clipboard Actions */}
      <div className="mt-4 pt-3.5 border-t border-neutral-100 dark:border-neutral-800/40 flex items-center justify-between">
        {/* Secondary Metadata Tags */}
        <div className="flex flex-wrap gap-1.5">
          {extraMetadata.map(([key, val]) => (
            <span
              key={key}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-neutral-100 dark:bg-neutral-900/60 text-neutral-500 dark:text-neutral-400"
            >
              <span className="opacity-60 mr-1 capitalize">{key}:</span>
              <span>{String(val)}</span>
            </span>
          ))}
        </div>

        {/* Copy Text Button */}
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center space-x-1 py-1 px-2.5 rounded-lg text-[10px] font-semibold tracking-tight border border-neutral-200 dark:border-neutral-800/80 bg-white dark:bg-neutral-900/60 hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200 transition-colors"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-emerald-500">Copied!</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
              </svg>
              <span>Copy snippet</span>
            </>
          )}
        </button>
      </div>
    </article>
  );
}

export function SearchDocs() {
  const [query, setQuery] = useState("");
  const [docType, setDocType] = useState<DocType | "">("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [status, setStatus] = useState<{ type: "loading" | "error" | "empty" | "success" | null; message: string }>({
    type: null,
    message: "",
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setStatus({ type: "loading", message: "Searching vectors…" });
    try {
      const results = await search(query, 5, docType || undefined);
      setHits(results);
      if (results.length === 0) {
        setStatus({ type: "empty", message: "No relevant documents found. Adjust query or type." });
      } else {
        setStatus({ type: "success", message: `Found ${results.length} matched passages.` });
      }
    } catch (err) {
      setStatus({ type: "error", message: (err as Error).message });
    }
  }

  return (
    <section className="space-y-6">
      {/* Search Input Control */}
      <div className="glass-panel rounded-2xl p-6 transition-all duration-300">
        <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider mb-4">
          Query Workspace
        </h2>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search compliance documents, e.g. transaction threshold"
              className="w-full pl-11 pr-4 py-3 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl text-sm placeholder-neutral-400 dark:placeholder-neutral-600 focus:outline-none input-minimalist"
            />
          </div>

          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between pt-1">
            {/* Filter tags/chips */}
            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <span className="text-xs font-medium text-neutral-400 dark:text-neutral-500 shrink-0">
                Filter:
              </span>
              <div className="flex p-0.5 rounded-lg bg-neutral-200/50 dark:bg-neutral-800/60 w-full sm:w-auto">
                {(["", "policy", "action"] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setDocType(type)}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-all duration-200 uppercase tracking-wider ${
                      docType === type
                        ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                        : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
                    }`}
                  >
                    {type === "" ? "All" : type}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={!query.trim()}
              className={`w-full sm:w-auto px-6 py-2 rounded-xl text-sm font-semibold tracking-tight text-white transition-all duration-300 ${
                !query.trim()
                  ? "bg-neutral-300 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-600 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/20 active:scale-[0.98]"
              }`}
            >
              Execute Search
            </button>
          </div>
        </form>
      </div>

      {/* Loading Skeleton */}
      {status.type === "loading" && (
        <div className="space-y-4">
          {[1, 2, 3].map((n) => (
            <div key={n} className="glass-panel rounded-2xl p-6 animate-pulse space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-4 bg-neutral-200 dark:bg-neutral-800 rounded w-1/4"></div>
                <div className="h-4 bg-neutral-200 dark:bg-neutral-800 rounded w-16"></div>
              </div>
              <div className="h-3 bg-neutral-200 dark:bg-neutral-800 rounded w-full"></div>
              <div className="h-3 bg-neutral-200 dark:bg-neutral-800 rounded w-5/6"></div>
            </div>
          ))}
        </div>
      )}

      {/* Status Panel (Error/Empty) */}
      {status.type && status.type !== "loading" && status.type !== "success" && (
        <div
          className={`p-4 rounded-xl text-xs flex items-center space-x-2.5 ${
            status.type === "error"
              ? "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20"
              : "bg-neutral-200/50 text-neutral-600 dark:bg-neutral-900/50 dark:text-neutral-400 border border-neutral-200/20"
          }`}
        >
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <span>{status.message}</span>
        </div>
      )}

      {/* Search Result Cards */}
      {status.type === "success" && hits.length > 0 && (
        <div className="space-y-4">
          <div className="text-xs font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider px-1">
            Search Results
          </div>
          <div className="space-y-4">
            {hits.map((hit) => (
              <SearchHitCard key={hit.id} hit={hit} query={query} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
