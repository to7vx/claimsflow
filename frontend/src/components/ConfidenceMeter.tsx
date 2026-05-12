import { clsx } from "clsx";

/**
 * Linear meter showing AI confidence. Color shifts: green > 0.9,
 * amber 0.7–0.9, red < 0.7.
 */
export function ConfidenceMeter({ value, className }: { value: number; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color =
    value >= 0.9 ? "bg-decision-approve" : value >= 0.7 ? "bg-decision-review" : "bg-decision-deny";

  return (
    <div className={clsx("flex items-center gap-2", className)}>
      <div
        className="h-1.5 w-24 rounded-full bg-bg-tertiary overflow-hidden"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={clsx("h-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-fg-secondary">{pct.toFixed(0)}%</span>
    </div>
  );
}
