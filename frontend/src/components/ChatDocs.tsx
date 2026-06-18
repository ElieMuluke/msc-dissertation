import { useState, useRef, useEffect } from "react";
import { streamAnswer, type DocType, type Citation } from "../api";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
  citations?: Citation[];
}

const STARTER_QUERIES = [
  "What is the suspicious transaction reporting threshold?",
  "What are the key red flags for money laundering?",
  "Summarize the Customer Identification Program requirements.",
  "What are the reporting duties for cash transactions over $10,000?"
];

// Parse inline markdown tokens: bold (**...**), italic (*...*), and citation brackets ([id])
function parseInlineMarkdown(
  text: string,
  citations?: Citation[],
  onSelectCitation?: (citation: Citation) => void
): React.ReactNode[] {
  if (!text) return [];

  // Match bold (**text**), italic (*text*), and citation brackets ([1], [doc_name], etc.)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[a-zA-Z0-9_\-]+\])/g;
  const parts = text.split(regex);

  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-neutral-900 dark:text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return (
        <em key={i} className="italic text-neutral-700 dark:text-neutral-300">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("[") && part.endsWith("]")) {
      const rawId = part.slice(1, -1);
      const citationExists = citations?.some(
        (c) => c.id.toLowerCase() === rawId.toLowerCase()
      );

      if (citationExists) {
        const matchingCitation = citations?.find(
          (c) => c.id.toLowerCase() === rawId.toLowerCase()
        );
        return (
          <span
            key={i}
            onClick={() => {
              if (matchingCitation && onSelectCitation) {
                onSelectCitation(matchingCitation);
              }
            }}
            className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 rounded text-[10px] font-mono font-bold select-none cursor-pointer bg-blue-600/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 hover:bg-blue-600/25 transition-all"
            title={`Source Citation [${rawId}]`}
          >
            {part}
          </span>
        );
      } else {
        return (
          <span key={i} className="text-neutral-500 dark:text-neutral-450 font-mono text-xs">
            {part}
          </span>
        );
      }
    }
    return part;
  });
}

// Render formatted message text with block-level lists and paragraphs
function FormattedMessageText({
  text,
  citations,
  onSelectCitation
}: {
  text: string;
  citations?: Citation[];
  onSelectCitation?: (citation: Citation) => void;
}) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  // State for grouping lists
  let currentListItems: { marker: string; content: string; key: number }[] = [];
  let currentListType: "ordered" | "unordered" | null = null;

  // State for accumulating paragraph lines
  let currentParagraphLines: string[] = [];

  const flushParagraph = (key: number) => {
    if (currentParagraphLines.length > 0) {
      const paraText = currentParagraphLines.join(" ");
      elements.push(
        <p key={`p-${key}`} className="text-sm leading-relaxed font-normal text-neutral-800 dark:text-neutral-200">
          {parseInlineMarkdown(paraText, citations, onSelectCitation)}
        </p>
      );
      currentParagraphLines = [];
    }
  };

  const flushList = (key: number) => {
    if (currentListItems.length === 0 || !currentListType) return;

    if (currentListType === "ordered") {
      elements.push(
        <div key={`ol-${key}`} className="space-y-3 my-3 pl-1">
          {currentListItems.map((item, idx) => (
            <div key={item.key} className="flex items-start space-x-3">
              <span className="text-blue-600 dark:text-blue-400 font-semibold text-xs shrink-0 select-none bg-blue-100 dark:bg-blue-900/40 w-5 h-5 rounded-full flex items-center justify-center font-mono shadow-sm">
                {idx + 1}
              </span>
              <p className="text-sm leading-relaxed font-normal text-neutral-850 dark:text-neutral-200 pt-0.5 flex-1">
                {parseInlineMarkdown(item.content, citations, onSelectCitation)}
              </p>
            </div>
          ))}
        </div>
      );
    } else {
      elements.push(
        <div key={`ul-${key}`} className="space-y-2.5 my-3 pl-1">
          {currentListItems.map((item) => (
            <div key={item.key} className="flex items-start space-x-3">
              <span className="text-blue-500 dark:text-blue-400 shrink-0 select-none flex items-center justify-center w-5 h-5 text-sm">
                •
              </span>
              <p className="text-sm leading-relaxed font-normal text-neutral-850 dark:text-neutral-200 pt-0.5 flex-1">
                {parseInlineMarkdown(item.content, citations, onSelectCitation)}
              </p>
            </div>
          ))}
        </div>
      );
    }

    currentListItems = [];
    currentListType = null;
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (trimmed === "") {
      flushList(idx);
      flushParagraph(idx);
      return;
    }

    // Match markdown headings (e.g. ### Headers)
    const headingMatch = line.match(/^\s*(#{1,6})\s+(.*)/);
    // Match unordered list items: -, *, •
    const unorderedMatch = line.match(/^\s*([•\-\*])\s+(.*)/);
    // Match ordered list items: 1. or 1)
    const orderedMatch = line.match(/^\s*(\d+)[.)]\s+(.*)/);

    if (headingMatch) {
      flushList(idx);
      flushParagraph(idx);
      const level = headingMatch[1].length;
      const headingContent = headingMatch[2];
      
      const headerClasses = 
        level === 1 ? "text-xl font-bold tracking-tight my-4" :
        level === 2 ? "text-lg font-bold tracking-tight my-3.5" :
        level === 3 ? "text-base font-semibold tracking-tight my-3" :
        "text-sm font-semibold tracking-tight my-2.5";

      elements.push(
        <h4 key={`h-${idx}`} className={`${headerClasses} text-neutral-900 dark:text-white`}>
          {parseInlineMarkdown(headingContent, citations, onSelectCitation)}
        </h4>
      );
    } else if (unorderedMatch) {
      flushParagraph(idx);
      if (currentListType !== "unordered") {
        flushList(idx);
        currentListType = "unordered";
      }
      currentListItems.push({
        marker: unorderedMatch[1],
        content: unorderedMatch[2],
        key: idx
      });
    } else if (orderedMatch) {
      flushParagraph(idx);
      if (currentListType !== "ordered") {
        flushList(idx);
        currentListType = "ordered";
      }
      currentListItems.push({
        marker: orderedMatch[1],
        content: orderedMatch[2],
        key: idx
      });
    } else {
      flushList(idx);
      currentParagraphLines.push(trimmed);
    }
  });

  // Flush remaining content at the end of the text
  flushList(lines.length);
  flushParagraph(lines.length);

  return <div className="space-y-3">{elements}</div>;
}

interface CitationRowProps {
  citation: Citation;
  onSelect: (citation: Citation) => void;
  isSelected: boolean;
}

// Single AI Citation/Source Detail Row
function CitationRow({ citation, onSelect, isSelected }: CitationRowProps) {
  const [copied, setCopied] = useState(false);

  // Score to Match Percent
  const matchPercent = citation.score >= 0 && citation.score <= 1
    ? (citation.score * 100).toFixed(1)
    : null;

  async function handleCopySource(e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const copyText = citation.text
        ? `Source: ${citation.source}, Page ${citation.page || "?"}\nContext: ${citation.text}`
        : `Source: ${citation.source}, Page ${citation.page || "?"}`;
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Copy failed", err);
    }
  }

  const rawText = citation.text || "";
  const cleanText = rawText.replace(/\s+/g, " ").trim();
  const truncatedText = cleanText.length > 150
    ? `${cleanText.substring(0, 147)}...`
    : cleanText;

  return (
    <div
      onClick={() => onSelect(citation)}
      className={`border rounded-xl p-3 text-xs flex flex-col space-y-1.5 cursor-pointer transition-all duration-300 ${
        isSelected
          ? "border-blue-500 bg-blue-500/5 dark:bg-blue-500/10 shadow-sm"
          : "border-neutral-150 dark:border-neutral-800/60 bg-neutral-50/50 dark:bg-neutral-900/20 hover:border-neutral-300 dark:hover:border-neutral-700"
      }`}
    >
      {/* Header Info */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center space-x-2 text-neutral-600 dark:text-neutral-355 font-medium truncate max-w-[200px]">
          <span className="bg-neutral-200 dark:bg-neutral-850 px-1.5 py-0.5 rounded font-mono font-bold text-[9px] text-neutral-500 dark:text-neutral-400 shrink-0">
            [{citation.id}]
          </span>
          <span className="truncate" title={citation.source}>
            {citation.source}
          </span>
          {citation.page !== undefined && (
            <span className="bg-neutral-105 dark:bg-neutral-900/80 px-1.5 py-0.2 rounded text-[10px] text-neutral-500">
              Pg {citation.page}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {matchPercent && (
            <span className="inline-flex items-center space-x-1 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] font-bold px-1.5 py-0.2 rounded-full shrink-0">
              {matchPercent}% Match
            </span>
          )}
          
          <button
            type="button"
            onClick={handleCopySource}
            className="text-[10px] text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-250 font-medium transition-colors"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {/* Truncated text preview inside reference card */}
      {cleanText && (
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <p className="text-[11px] text-neutral-500 dark:text-neutral-450 leading-relaxed font-normal italic truncate flex-1 font-sans">
            "{truncatedText}"
          </p>
          <span className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold shrink-0 flex items-center space-x-0.5">
            <span>View</span>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </span>
        </div>
      )}
    </div>
  );
}

interface ChatDocsProps {
  dbStatus?: "connected" | "disconnected";
  llmStatus?: "connected" | "disconnected";
}

export function ChatDocs({ dbStatus, llmStatus }: ChatDocsProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [docType, setDocType] = useState<DocType | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [copiedSelected, setCopiedSelected] = useState(false);
  
  const abortControllerRef = useRef<AbortController | null>(null);

  // Clean up ongoing stream on component unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  async function handleCopySelectedText() {
    if (!selectedCitation) return;
    try {
      await navigator.clipboard.writeText(
        `Source: ${selectedCitation.source}, Page ${selectedCitation.page || "?"}\nContext: ${selectedCitation.text}`
      );
      setCopiedSelected(true);
      setTimeout(() => setCopiedSelected(false), 2000);
    } catch (err) {
      console.error("Copy failed", err);
    }
  }

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(queryText: string) {
    if (!queryText.trim() || loading) return;

    setError(null);
    const userMessage: Message = {
      id: Math.random().toString(36).substring(7),
      role: "user",
      text: queryText,
      timestamp: new Date()
    };

    const assistantMessageId = Math.random().toString(36).substring(7);
    const assistantPlaceholder: Message = {
      id: assistantMessageId,
      role: "assistant",
      text: "",
      timestamp: new Date(),
      citations: []
    };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setInput("");
    setLoading(true);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let accumulatedText = "";
      await streamAnswer(
        { query: queryText, doc_type: docType || undefined },
        {
          onToken: (token) => {
            setLoading(false); // Hide the bounce skeleton as soon as the first token arrives
            accumulatedText += token;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, text: accumulatedText }
                  : msg
              )
            );
          },
          onDone: (citations) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, citations }
                  : msg
              )
            );
            setLoading(false);
          },
          onError: (errMsg) => {
            setError(errMsg);
            setLoading(false);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId && !msg.text
                  ? { ...msg, text: `⚠️ Generation failed: ${errMsg}` }
                  : msg
              )
            );
          }
        },
        controller.signal
      );
    } catch (err) {
      if (controller.signal.aborted) return;
      setError((err as Error).message);
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      setLoading(false);
    }
  }

  function handleClear() {
    if (window.confirm("Clear conversation history?")) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      setMessages([]);
      setError(null);
      setSelectedCitation(null);
      setLoading(false);
    }
  }

  return (
    <section className="flex flex-col space-y-6 min-h-[500px]">
      {/* Database Offline Indicator */}
      {dbStatus === "disconnected" && (
        <div className="p-4 rounded-xl text-xs bg-rose-500/10 text-rose-600 dark:text-rose-455 border border-rose-500/20 flex items-center space-x-2.5">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span><strong>Vector Database Offline:</strong> Chat capabilities are disabled until connection is restored.</span>
        </div>
      )}

      {/* LLM Offline Indicator */}
      {dbStatus === "connected" && llmStatus === "disconnected" && (
        <div className="p-3.5 rounded-xl text-xs bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 flex items-start space-x-2.5 leading-normal">
          <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>
            <strong>LLM Generator Offline:</strong> The local generative model (Ollama) is currently offline or unconfigured. 
            All queries will degrade gracefully to use the semantic search fallback.
          </span>
        </div>
      )}

      {/* Search/Query Options Panel */}
      <div className="glass-panel rounded-2xl p-6 transition-all duration-300">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
            Compliance RAG Chat
          </h2>
          
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-neutral-400 dark:text-neutral-500 shrink-0">Filter:</span>
            <div className="flex p-0.5 rounded-lg bg-neutral-200/50 dark:bg-neutral-800/60">
              {(["", "policy", "action"] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setDocType(type)}
                  className={`px-2.5 py-0.5 text-[10px] font-semibold rounded transition-all duration-200 uppercase tracking-wider ${
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
        </div>

        <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
          Ask clarifying compliance questions. The system will retrieve relevant source chunks, cite them inline, and generate an answer.
        </p>
      </div>

      {/* Main Conversation & Citation Side Panel Container */}
      <div className="flex flex-col lg:flex-row gap-6 items-stretch relative min-h-[450px] lg:min-h-[550px]">
        
        {/* Chat Thread Panel */}
        <div className={`glass-panel rounded-2xl p-6 flex-1 flex flex-col justify-between min-h-[400px] max-h-[600px] overflow-hidden border border-neutral-200/50 dark:border-neutral-855 bg-white/40 dark:bg-neutral-900/10 transition-all duration-300 ${
          selectedCitation ? "lg:max-w-[60%] lg:flex-1" : "w-full"
        }`}>
          {/* Messages scrollable viewport */}
          <div className="flex-1 overflow-y-auto space-y-5 pr-1 mb-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
                {/* Shield/Chat Icon */}
                <div className="p-4 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-500 mb-4 animate-pulse">
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200 mb-1.5">
                  Compliance Agent Ready
                </h3>
                <p className="text-xs text-neutral-400 dark:text-neutral-500 max-w-sm">
                  Select one of the topics below or type your inquiry.
                </p>

                {/* Suggestions Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-6 w-full max-w-lg">
                  {STARTER_QUERIES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSend(q)}
                      disabled={dbStatus === "disconnected"}
                      className="p-3 text-left rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-blue-500/40 hover:bg-neutral-50 dark:hover:bg-neutral-900/60 transition-all text-xs text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {/* Messages Thread */}
                {messages.map((msg) => {
                  const isUser = msg.role === "user";
                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4.5 py-3.5 shadow-sm text-sm leading-relaxed ${
                          isUser
                            ? "bg-blue-600 text-white dark:bg-blue-600/20 dark:text-blue-100 border border-blue-600/10"
                            : "bg-neutral-50/90 text-neutral-800 dark:bg-neutral-900/80 dark:text-neutral-200 border border-neutral-200/50 dark:border-neutral-800/80"
                        }`}
                      >
                        {/* Message Text */}
                        <FormattedMessageText
                          text={msg.text}
                          citations={msg.citations}
                          onSelectCitation={setSelectedCitation}
                        />

                        {/* Assistant Citations Footer */}
                        {!isUser && msg.citations && msg.citations.length > 0 && (
                          <div className="mt-4 pt-3 border-t border-neutral-200/30 dark:border-neutral-800/55 space-y-2">
                            <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                              Source References
                            </p>
                            <div className="grid grid-cols-1 gap-2">
                              {msg.citations.map((cit) => (
                                <CitationRow
                                  key={cit.id}
                                  citation={cit}
                                  onSelect={setSelectedCitation}
                                  isSelected={selectedCitation?.id === cit.id && selectedCitation?.source === cit.source}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Timestamp */}
                      <span className="text-[9px] text-neutral-400 dark:text-neutral-500 mt-1.5 px-2">
                        {msg.timestamp.toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit"
                        })}
                      </span>
                    </div>
                  );
                })}
              </>
            )}

            {/* Typing Loading Skeleton */}
            {loading && (
              <div className="flex flex-col items-start">
                <div className="glass-panel rounded-2xl px-5 py-4 w-2/3 border border-neutral-200/50 dark:border-neutral-800/80 space-y-2.5">
                  <div className="flex space-x-1 items-center pb-2">
                    <span className="h-1.5 w-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                    <span className="h-1.5 w-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="h-1.5 w-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </div>
                  <div className="h-3 bg-neutral-200 dark:bg-neutral-800 rounded w-full animate-pulse"></div>
                  <div className="h-3 bg-neutral-200 dark:bg-neutral-800 rounded w-5/6 animate-pulse"></div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Errors view */}
          {error && (
            <div className="p-3 mb-3 text-xs bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 rounded-xl flex items-center space-x-2">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* Input box */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            className="flex items-center space-x-2 border-t border-neutral-100 dark:border-neutral-800/60 pt-4"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading || dbStatus === "disconnected"}
              placeholder={dbStatus === "disconnected" ? "Database offline, chat disabled..." : "Ask anything about ingested compliance documents..."}
              className="flex-1 px-4 py-2.5 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl text-xs placeholder-neutral-400 dark:placeholder-neutral-600 focus:outline-none input-minimalist disabled:opacity-50 disabled:cursor-not-allowed"
            />
            
            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleClear}
                className="p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-855 hover:bg-red-500/5 hover:text-red-500 transition-colors text-neutral-400"
                title="Clear Chat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}

            <button
              type="submit"
              disabled={!input.trim() || loading || dbStatus === "disconnected"}
              className={`px-4.5 py-2.5 rounded-xl text-xs font-semibold tracking-tight text-white transition-all duration-300 ${
                !input.trim() || loading || dbStatus === "disconnected"
                  ? "bg-neutral-300 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-600 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/20 active:scale-[0.98]"
              }`}
            >
              {dbStatus === "disconnected" ? "Offline" : "Send"}
            </button>
          </form>
        </div>

        {/* Selected Citation Side Panel */}
        {selectedCitation && (
          <div className="w-full lg:w-[40%] lg:h-[600px] flex flex-col glass-panel rounded-2xl p-5 border border-blue-500/20 dark:border-blue-500/30 bg-white/95 dark:bg-neutral-900/90 shadow-xl shrink-0 transition-all duration-300">
            {/* Panel Header */}
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800/80 pb-3 mb-4 shrink-0">
              <div className="flex items-center space-x-2">
                <span className="bg-blue-600/10 dark:bg-blue-500/25 px-2 py-0.5 rounded font-mono font-bold text-xs text-blue-600 dark:text-blue-400">
                  [{selectedCitation.id}]
                </span>
                <span className="text-xs font-bold text-neutral-850 dark:text-neutral-200">
                  Reference Context
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCitation(null)}
                className="p-1 rounded-full text-neutral-450 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-850 transition-colors"
                aria-label="Close reference panel"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Document metadata info */}
            <div className="space-y-2 mb-4 shrink-0 text-xs text-neutral-500 dark:text-neutral-450 bg-neutral-50 dark:bg-neutral-950 p-3.5 rounded-xl border border-neutral-200/40 dark:border-neutral-850">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-neutral-800 dark:text-neutral-300 truncate max-w-[200px]" title={selectedCitation.source}>
                  {selectedCitation.source}
                </span>
                {selectedCitation.page !== undefined && (
                  <span className="bg-neutral-200 dark:bg-neutral-850 px-2 py-0.5 rounded font-semibold text-[10px] text-neutral-650 dark:text-neutral-350">
                    Page {selectedCitation.page}
                  </span>
                )}
              </div>
              
              <div className="flex items-center justify-between pt-1.5 border-t border-neutral-200/30 dark:border-neutral-850">
                <span>Similarity Match:</span>
                {selectedCitation.score !== undefined ? (
                  <span className="font-bold text-emerald-600 dark:text-emerald-450">
                    {(selectedCitation.score * 100).toFixed(1)}% Match
                  </span>
                ) : (
                  <span>N/A</span>
                )}
              </div>
            </div>

            {/* Full scrollable content block */}
            <div className="flex-1 overflow-y-auto pr-1">
              <p className="text-xs leading-relaxed text-neutral-700 dark:text-neutral-300 font-normal bg-neutral-50/40 dark:bg-neutral-950/20 p-3.5 rounded-xl border border-neutral-100 dark:border-neutral-900/60 shadow-inner italic whitespace-pre-line">
                "{selectedCitation.text || "No full-text context available for this reference."}"
              </p>
            </div>

            {/* Footer Copy option */}
            <div className="pt-3 border-t border-neutral-100 dark:border-neutral-800/80 mt-4 shrink-0 flex justify-end">
              <button
                type="button"
                onClick={handleCopySelectedText}
                className="inline-flex items-center space-x-1.5 py-1.5 px-3.5 rounded-lg text-xs font-semibold tracking-tight border border-neutral-200 dark:border-neutral-855 bg-white dark:bg-neutral-905 hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-600 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200 transition-colors"
              >
                {copiedSelected ? (
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
                    <span>Copy full text</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
