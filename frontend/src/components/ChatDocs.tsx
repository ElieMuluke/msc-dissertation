import { useState, useRef, useEffect } from "react";
import { askQuestion, type DocType, type Citation } from "../api";

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

// Highlight references such as [1] or [abc] inline within the text
function InlineCitationHighlighter({ text, citations }: { text: string; citations?: Citation[] }) {
  if (!text) return null;

  // Regex to match citation brackets like [1], [a], [chunk_0], etc.
  const citationRegex = /(\[[a-zA-Z0-9_\-]+\])/g;
  const parts = text.split(citationRegex);

  return (
    <>
      {parts.map((part, i) => {
        const isCitation = citationRegex.test(part);
        if (isCitation) {
          const rawId = part.slice(1, -1);
          // Check if it matches an actual citation ID in our metadata
          const citationExists = citations?.some(
            (c) => c.id.toLowerCase() === rawId.toLowerCase()
          );

          return (
            <span
              key={i}
              className={`inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 rounded text-[10px] font-mono font-bold select-none cursor-pointer transition-all ${
                citationExists
                  ? "bg-blue-600/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20"
                  : "bg-neutral-200 dark:bg-neutral-800 text-neutral-500"
              }`}
              title={citationExists ? `Source Citation [${rawId}]` : undefined}
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

// Render formatted message text with paragraph breaks and lists
function FormattedMessageText({ text, citations }: { text: string; citations?: Citation[] }) {
  if (!text) return null;

  // Split paragraphs
  const paragraphs = text.split(/\n\s*\n/).filter(Boolean);

  return (
    <div className="space-y-3">
      {paragraphs.map((para, pIdx) => {
        // Detect bulleted lists
        const listRegex = /^([\*•\-]|^\d+\.)\s+(.*)/;
        const listMatch = para.match(listRegex);

        if (listMatch) {
          const content = listMatch[2];
          return (
            <div key={pIdx} className="flex items-start space-x-2 pl-1.5">
              <span className="text-blue-500 dark:text-blue-400 mt-1.5 shrink-0 text-[10px]">&bull;</span>
              <p className="text-sm leading-relaxed font-normal">
                <InlineCitationHighlighter text={content} citations={citations} />
              </p>
            </div>
          );
        }

        return (
          <p key={pIdx} className="text-sm leading-relaxed font-normal">
            <InlineCitationHighlighter text={para} citations={citations} />
          </p>
        );
      })}
    </div>
  );
}

// Single AI Citation/Source Detail Row
function CitationRow({ citation }: { citation: Citation }) {
  const [copied, setCopied] = useState(false);

  // Score to Match Percent
  const matchPercent = citation.score >= 0 && citation.score <= 1
    ? (citation.score * 100).toFixed(1)
    : null;

  async function handleCopySource() {
    try {
      await navigator.clipboard.writeText(`Source: ${citation.source}, Page ${citation.page || "?"}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Copy failed", err);
    }
  }

  return (
    <div className="border border-neutral-150 dark:border-neutral-800/60 rounded-xl bg-neutral-50/50 dark:bg-neutral-900/20 p-3 text-xs flex flex-col space-y-2 hover:border-neutral-200 dark:hover:border-neutral-800 transition-colors">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center space-x-2 text-neutral-600 dark:text-neutral-300 font-medium truncate max-w-[240px]">
          <span className="bg-neutral-200 dark:bg-neutral-850 px-1.5 py-0.5 rounded font-mono font-bold text-[9px] text-neutral-500 dark:text-neutral-400 shrink-0">
            [{citation.id}]
          </span>
          <span className="truncate" title={citation.source}>
            {citation.source}
          </span>
          {citation.page !== undefined && (
            <span className="bg-neutral-100 dark:bg-neutral-900/80 px-1.5 py-0.2 rounded text-[10px] text-neutral-500">
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
            className="text-[10px] text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
          >
            {copied ? "Copied" : "Copy Ref"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChatDocs() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [docType, setDocType] = useState<DocType | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await askQuestion(queryText, docType || undefined);

      const assistantMessage: Message = {
        id: Math.random().toString(36).substring(7),
        role: "assistant",
        text: response.answer,
        timestamp: new Date(),
        citations: response.citations
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    if (window.confirm("Clear conversation history?")) {
      setMessages([]);
      setError(null);
    }
  }

  return (
    <section className="flex flex-col space-y-6 min-h-[500px]">
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

      {/* Main Conversation Container */}
      <div className="glass-panel rounded-2xl p-6 flex-1 flex flex-col justify-between min-h-[400px] max-h-[600px] overflow-hidden border border-neutral-200/50 dark:border-neutral-850 bg-white/40 dark:bg-neutral-900/10">
        
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
                    className="p-3 text-left rounded-xl border border-neutral-200 dark:border-neutral-800 hover:border-blue-500/40 hover:bg-neutral-50 dark:hover:bg-neutral-900/60 transition-all text-xs text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200"
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
                      <FormattedMessageText text={msg.text} citations={msg.citations} />

                      {/* Assistant Citations Footer */}
                      {!isUser && msg.citations && msg.citations.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-neutral-200/30 dark:border-neutral-800/50 space-y-2">
                          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                            Source References
                          </p>
                          <div className="grid grid-cols-1 gap-2">
                            {msg.citations.map((cit) => (
                              <CitationRow key={cit.id} citation={cit} />
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
            disabled={loading}
            placeholder="Ask anything about ingested compliance documents..."
            className="flex-1 px-4 py-2.5 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl text-xs placeholder-neutral-400 dark:placeholder-neutral-600 focus:outline-none input-minimalist"
          />
          
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className="p-2.5 rounded-xl border border-neutral-200 dark:border-neutral-850 hover:bg-red-500/5 hover:text-red-500 transition-colors text-neutral-400"
              title="Clear Chat"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}

          <button
            type="submit"
            disabled={!input.trim() || loading}
            className={`px-4.5 py-2.5 rounded-xl text-xs font-semibold tracking-tight text-white transition-all duration-300 ${
              !input.trim() || loading
                ? "bg-neutral-300 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-600 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-500/20 active:scale-[0.98]"
            }`}
          >
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
