import { useEffect, useState } from "react";
import { useExceptionQueue } from "@/lib/hooks";
import { ExceptionSidePanel } from "@/components/ExceptionSidePanel";
import { Badge } from "@/components/Badge";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { SkeletonRows } from "@/components/Skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatSAR } from "@/lib/format";
import type { QueueItem } from "@/lib/types";

export default function ExceptionQueue() {
  const { data, isLoading } = useExceptionQueue();
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [cursor, setCursor] = useState(0);

  useEffect(() => {
    if (selected) return;
    const handler = (e: KeyboardEvent) => {
      if (!data || data.length === 0) return;
      if (e.key === "j" || e.key === "J") setCursor((c) => Math.min(c + 1, data.length - 1));
      if (e.key === "k" || e.key === "K") setCursor((c) => Math.max(c - 1, 0));
      if (e.key === "Enter") setSelected(data[cursor]);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [data, cursor, selected]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Exception queue</h1>
          <p className="text-sm text-fg-secondary mt-1">
            Sorted by priority (SLA · amount · 1 − confidence). Use{" "}
            <kbd className="font-mono text-xs px-1.5 py-0.5 rounded bg-bg-tertiary border border-border">
              J/K
            </kbd>{" "}
            to navigate,{" "}
            <kbd className="font-mono text-xs px-1.5 py-0.5 rounded bg-bg-tertiary border border-border">
              Enter
            </kbd>{" "}
            to open.
          </p>
        </div>
      </header>

      {isLoading ? (
        <SkeletonRows rows={8} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Queue clear"
          message="Nothing to review right now. New exceptions appear here in real time."
        />
      ) : (
        <div className="panel divide-y divide-border-subtle">
          {data.map((item, i) => (
            <button
              key={item.claim.claim_id}
              className={`w-full grid grid-cols-12 items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-bg-tertiary/50 ${
                i === cursor ? "bg-bg-tertiary/70" : ""
              }`}
              onClick={() => setSelected(item)}
            >
              <span className="col-span-2 font-mono text-xs text-fg-muted">{item.claim.claim_id}</span>
              <span className="col-span-3 truncate">
                {item.member.full_name_en}
                <span className="text-fg-muted text-xs ml-2">{item.provider.name_en}</span>
              </span>
              <span className="col-span-2 font-mono text-xs text-fg-secondary">
                {item.claim.diagnosis_codes.join(", ")}
              </span>
              <span className="col-span-2 font-mono text-sm tabular-nums">
                {formatSAR(item.claim.total_billed)}
              </span>
              <span className="col-span-2">
                {item.decision && <ConfidenceMeter value={item.decision.confidence_score} />}
              </span>
              <span className="col-span-1 text-right">
                <Badge tone="review">{item.sla_age_days}d</Badge>
              </span>
            </button>
          ))}
        </div>
      )}

      <ExceptionSidePanel item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
