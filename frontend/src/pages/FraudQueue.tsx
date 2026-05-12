import { useState } from "react";
import { useFraudQueue } from "@/lib/hooks";
import { ExceptionSidePanel } from "@/components/ExceptionSidePanel";
import { Badge } from "@/components/Badge";
import { SkeletonRows } from "@/components/Skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatSAR } from "@/lib/format";
import type { QueueItem } from "@/lib/types";

export default function FraudQueue() {
  const { data, isLoading } = useFraudQueue();
  const [selected, setSelected] = useState<QueueItem | null>(null);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Fraud holds</h1>
        <p className="text-sm text-fg-secondary mt-1">
          Claims flagged by rules + LLM reasoning. Investigate before deciding.
        </p>
      </header>

      {isLoading ? (
        <SkeletonRows rows={6} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="No active holds" message="Nothing currently flagged for fraud." />
      ) : (
        <div className="panel divide-y divide-border-subtle">
          {data.map((item) => (
            <button
              key={item.claim.claim_id}
              className="w-full grid grid-cols-12 items-center gap-3 px-5 py-3 text-left hover:bg-bg-tertiary/50"
              onClick={() => setSelected(item)}
            >
              <span className="col-span-2 font-mono text-xs text-fg-muted">{item.claim.claim_id}</span>
              <span className="col-span-3 truncate">{item.provider.name_en}</span>
              <span className="col-span-3 truncate text-sm text-fg-secondary">
                {(item.decision?.flags ?? []).slice(0, 3).join(" · ")}
              </span>
              <span className="col-span-2 font-mono text-sm tabular-nums">
                {formatSAR(item.claim.total_billed)}
              </span>
              <span className="col-span-2 text-right">
                <Badge tone="fraud">
                  risk {item.decision ? Math.round(item.decision.confidence_score * 100) : "—"}
                </Badge>
              </span>
            </button>
          ))}
        </div>
      )}

      <ExceptionSidePanel item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
