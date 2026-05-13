import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { api } from "@/lib/api";
import { useDemoStatus } from "@/lib/hooks";

/**
 * Run / Clear demo controls for the Overview page.
 *
 * - "Run Live Demo" submits 10 mixed claims with 2s gaps via the backend.
 * - "Clear Demo Data" drops the DB, re-seeds, and adjudicates 25 samples.
 *
 * Both poll /api/v1/demo/status while running so the buttons can show
 * "Running… N/10". Toast on completion.
 */
export function DemoControls() {
  const qc = useQueryClient();
  const [confirmReset, setConfirmReset] = useState(false);
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "err" } | null>(null);

  // Poll status fast while a job is running, slow otherwise.
  const { data: status } = useDemoStatus(true, false);
  const isRunning = !!status && status.finished_at == null && status.error == null;
  // Once we know a job is running, switch to fast polling.
  useDemoStatus(isRunning, true);

  // When the job transitions running -> done, invalidate dashboard caches.
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!status) return;
    if (status.finished_at && status.job_id !== lastJobId) {
      setLastJobId(status.job_id);
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["decisions-breakdown"] });
      qc.invalidateQueries({ queryKey: ["claims", "recent"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      setToast({
        text:
          status.error
            ? `${status.kind === "run" ? "Run" : "Reset"} failed: ${status.error}`
            : status.kind === "run"
            ? "Live demo complete · 10 claims submitted"
            : "Demo data reset · seed + 25 decisions restored",
        tone: status.error ? "err" : "ok",
      });
      const t = setTimeout(() => setToast(null), 4500);
      return () => clearTimeout(t);
    }
  }, [status, lastJobId, qc]);

  const runMut = useMutation({
    mutationFn: () => api.demoRun(),
    onError: (e: Error) => setToast({ text: e.message, tone: "err" }),
  });
  const resetMut = useMutation({
    mutationFn: () => api.demoReset(),
    onError: (e: Error) => setToast({ text: e.message, tone: "err" }),
    onSettled: () => setConfirmReset(false),
  });

  const disabled = isRunning || runMut.isPending || resetMut.isPending;

  let runLabel = "▶ Run live demo";
  if (isRunning && status?.kind === "run") runLabel = `Running… ${status.current}/${status.total}`;
  let resetLabel = "↺ Clear demo data";
  if (isRunning && status?.kind === "reset") {
    const phase = ["", "dropping…", "seeding…", "adjudicating…", "finishing…"][status.current] ?? "";
    resetLabel = `Resetting · ${phase}`;
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => runMut.mutate()}
          disabled={disabled}
          className={clsx(
            "inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm font-medium transition-all",
            "bg-accent text-bg-primary hover:bg-accent-hover",
            "disabled:opacity-60 disabled:cursor-not-allowed",
            !disabled && "shadow-[0_0_0_0_rgba(70,229,181,0.4)] hover:shadow-[0_0_0_4px_rgba(70,229,181,0.18)]",
          )}
        >
          {isRunning && status?.kind === "run" && (
            <span className="h-1.5 w-1.5 rounded-full bg-bg-primary animate-pulse-live" />
          )}
          {runLabel}
        </button>

        <button
          type="button"
          onClick={() => setConfirmReset(true)}
          disabled={disabled}
          className={clsx(
            "inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm font-mono",
            "border border-border text-fg-secondary hover:text-fg-primary hover:border-decision-review",
            "disabled:opacity-60 disabled:cursor-not-allowed",
          )}
        >
          {isRunning && status?.kind === "reset" && (
            <span className="h-1.5 w-1.5 rounded-full bg-decision-review animate-pulse-live" />
          )}
          {resetLabel}
        </button>
      </div>

      {confirmReset && (
        <ResetConfirm
          onConfirm={() => resetMut.mutate()}
          onCancel={() => setConfirmReset(false)}
          pending={resetMut.isPending}
        />
      )}

      {toast && (
        <div
          className={clsx(
            "fixed bottom-6 right-6 z-50 max-w-md rounded border px-4 py-3 text-sm shadow-panel",
            "animate-slide-in-right",
            toast.tone === "ok"
              ? "bg-bg-elevated border-accent text-fg-primary"
              : "bg-bg-elevated border-decision-deny text-decision-deny",
          )}
          role="status"
        >
          {toast.text}
        </div>
      )}
    </>
  );
}

function ResetConfirm({
  onConfirm,
  onCancel,
  pending,
}: {
  onConfirm: () => void;
  onCancel: () => void;
  pending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div
        className="panel max-w-md w-full mx-4 p-6 animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold">Reset demo data?</h3>
        <p className="text-sm text-fg-secondary mt-2 leading-relaxed">
          This drops every table, re-seeds 5 plans / 20 providers / 50 members / 100 claims, then
          adjudicates 25 sample claims so the dashboard is populated. Takes ~3 minutes on local
          Ollama. The current claims and decisions will be deleted.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={pending}
            className="px-3 py-1.5 text-sm font-mono text-fg-secondary hover:text-fg-primary disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={pending}
            className="px-3 py-1.5 rounded bg-decision-review text-bg-primary text-sm font-medium hover:opacity-90 disabled:opacity-60"
          >
            {pending ? "Starting…" : "Reset"}
          </button>
        </div>
      </div>
    </div>
  );
}
