import { clsx } from "clsx";

export function HeroMetric({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="panel p-5 flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</span>
      <span
        className={clsx(
          "font-semibold tabular-nums",
          accent ? "text-accent text-3xl" : "text-fg-primary text-2xl",
        )}
      >
        {value}
      </span>
      {sub && <span className="text-xs text-fg-secondary">{sub}</span>}
    </div>
  );
}
