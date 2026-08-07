import { useRef, useState } from "react";
import {
  runAnalysis,
  reportDownloadUrl,
  type AnalysisDone,
  type AnalysisStep,
  type Pipeline,
} from "../api";

const DECISION_STYLES: Record<string, string> = {
  escalate: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30",
  investigate: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30",
  dismiss: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
};

function stepLabel(step: AnalysisStep): string {
  const extras = Object.entries(step)
    .filter(([key]) => key !== "stage")
    .map(([, value]) => String(value))
    .join(" · ");
  return extras ? `${step.stage} — ${extras}` : step.stage;
}

export function CaseAnalysis() {
  const [accountId, setAccountId] = useState("");
  const [bank, setBank] = useState("");
  const [pipeline, setPipeline] = useState<Pipeline>("single");
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<AnalysisStep[]>([]);
  const [result, setResult] = useState<AnalysisDone | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId.trim() || running) return;
    setRunning(true);
    setSteps([]);
    setResult(null);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;

    await runAnalysis(
      {
        account_id: accountId.trim(),
        bank: bank.trim() || undefined,
        pipeline,
      },
      {
        onStep: (step) => setSteps((prev) => [...prev, step]),
        onDone: (done) => setResult(done),
        onError: (message) => setError(message),
      },
      controller.signal
    );
    setRunning(false);
  }

  function onCancel() {
    abortRef.current?.abort();
    setRunning(false);
  }

  return (
    <section className="glass-panel rounded-2xl p-6 space-y-6 min-w-0 w-full">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
          Case Analysis
        </h2>

        {/* Pipeline toggle: single agent vs multi-agent (LangGraph) pipeline */}
        <div className="flex p-0.5 rounded-lg bg-neutral-200/50 dark:bg-neutral-800/60">
          {(["single", "mas"] as Pipeline[]).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPipeline(p)}
              disabled={running}
              title={p === "single" ? "Monolithic single agent" : "Multi-agent pipeline (Orchestrator → Data → Policy & Risk → Reporting)"}
              className={`px-3 py-1 text-[11px] font-semibold rounded-md transition-all duration-200 uppercase tracking-wider ${
                pipeline === p
                  ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                  : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
              }`}
            >
              {p === "single" ? "Single Agent" : "Multi-Agent"}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={onSubmit} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 sm:items-start">
        <div className="min-w-0 space-y-1">
          <input
            type="text"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            placeholder="Account number (e.g. 80171BEE0)"
            className="w-full px-4 py-2.5 rounded-xl text-sm bg-white/60 dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800 focus:outline-none focus:ring-2 focus:ring-blue-500/40 min-w-0"
            disabled={running}
          />
          <p className="px-1 text-[11px] leading-snug text-neutral-400 dark:text-neutral-500">
            IBM account ids are alphanumeric (e.g. 80171BEE0) and effectively unique.
          </p>
        </div>
        <div className="min-w-0 space-y-1">
          <input
            type="text"
            value={bank}
            onChange={(e) => setBank(e.target.value)}
            placeholder="Bank id (optional)"
            className="w-full px-4 py-2.5 rounded-xl text-sm bg-white/60 dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800 focus:outline-none focus:ring-2 focus:ring-blue-500/40 min-w-0"
            disabled={running}
          />
          <p className="px-1 text-[11px] leading-snug text-neutral-400 dark:text-neutral-500">
            Bank ids are numeric with no leading zeros (e.g. 2597) — rarely needed.
          </p>
        </div>
        {running ? (
          <button
            type="button"
            onClick={onCancel}
            className="py-2.5 px-5 rounded-xl text-sm font-semibold border border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-all"
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            disabled={!accountId.trim()}
            className="py-2.5 px-5 rounded-xl text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Analyse
          </button>
        )}
      </form>

      {/* Live agent-step stream */}
      {(steps.length > 0 || running) && (
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/40 dark:bg-neutral-900/40 p-4 max-h-56 overflow-y-auto">
          <ol className="space-y-1.5 text-xs font-mono text-neutral-600 dark:text-neutral-400">
            {steps.map((step, i) => (
              <li key={i} className="flex items-start space-x-2">
                <span className="text-emerald-500 shrink-0 mt-[1px]">✓</span>
                <span className="break-all">{stepLabel(step)}</span>
              </li>
            ))}
            {running && (
              <li className="flex items-center space-x-2 text-neutral-400">
                <span className="animate-pulse">●</span>
                <span>running…</span>
              </li>
            )}
          </ol>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-xl text-xs bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
          {error}
        </div>
      )}

      {/* Decision card */}
      {result && (
        <div
          className={`rounded-xl border p-5 space-y-3 ${
            DECISION_STYLES[result.decision] ?? "bg-neutral-500/10 text-neutral-600 dark:text-neutral-300 border-neutral-500/30"
          }`}
        >
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-lg font-bold uppercase tracking-wide">{result.decision}</span>
            <span className="text-[10px] uppercase tracking-wider opacity-70">
              pipeline: {result.pipeline}
            </span>
          </div>
          <p className="text-sm leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
            {result.rationale}
          </p>
          <a
            href={reportDownloadUrl(result.report_id)}
            download
            className="inline-flex items-center space-x-2 text-xs font-semibold underline underline-offset-2 hover:opacity-75"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
            </svg>
            <span>Download audit report ({result.report_id.slice(0, 8)}…)</span>
          </a>
        </div>
      )}
    </section>
  );
}
