import { useEffect, useState } from "react";
import { getExperimentProgress, type ExperimentProgress as Progress } from "../api";

/**
 * Repeatability-experiment progress panel (PRD-B §6): polls the thin backend route
 * over experiments/results/progress.json while the weekend sweep runs. Shows a quiet
 * "no sweep running" note until the runner has written the file.
 */
export function ExperimentProgress() {
  const [progress, setProgress] = useState<Progress>({ available: false });

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const data = await getExperimentProgress();
      if (!cancelled) setProgress(data);
    }
    poll();
    const interval = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const done = typeof progress.done === "number" ? progress.done : null;
  const total = typeof progress.total === "number" ? progress.total : null;
  const pct = done !== null && total ? Math.min(100, Math.round((done / total) * 100)) : null;

  return (
    <section className="glass-panel rounded-2xl p-6 min-w-0 w-full">
      <h2 className="text-sm font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
        Experiment Sweep
      </h2>

      {!progress.available ? (
        <p className="mt-4 text-xs text-neutral-500 dark:text-neutral-400">
          No sweep running (experiments/results/progress.json not found).
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {pct !== null && (
            <>
              <div className="flex justify-between text-xs text-neutral-500 dark:text-neutral-400">
                <span>
                  {done!.toLocaleString()} / {total!.toLocaleString()} runs
                </span>
                <span className="font-semibold">{pct}%</span>
              </div>
              <div className="h-2 rounded-full bg-neutral-200/60 dark:bg-neutral-800/80 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-700"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </>
          )}
          {typeof progress.eta === "string" && (
            <p className="text-[11px] text-neutral-500 dark:text-neutral-400">ETA: {progress.eta}</p>
          )}
          {typeof progress.last_run === "string" && (
            <p className="text-[11px] text-neutral-500 dark:text-neutral-400">
              Last run: {progress.last_run}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
