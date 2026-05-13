import { useState } from "react";
import { useFraudQueue } from "@/lib/hooks";
import { ExceptionSidePanel } from "@/components/ExceptionSidePanel";
import { Badge } from "@/components/Badge";
import { LiveBadge } from "@/components/LiveBadge";
import { SkeletonRows } from "@/components/Skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatSAR } from "@/lib/format";
import type { QueueItem } from "@/lib/types";

const FRAUD_SIGNAL_LABEL: Record<string, string> = {
  duplicate_within_7d: "Duplicate",
  provider_velocity: "Velocity",
  amount_anomaly: "Amount anomaly",
  pediatric_diagnosis_on_adult: "Pediatric dx on adult",
};

function fraudSignalChips(flags: string[]): React.ReactNode {
  const seen = new Set<string>();
  const chips: React.ReactNode[] = [];
  for (const f of flags) {
    let label: string | null = null;
    if (f.startsWith("fraud_signal:")) {
      const key = f.slice("fraud_signal:".length);
      label = FRAUD_SIGNAL_LABEL[key] ?? key.replace(/_/g, " ");
    } else if (f === "high_fraud_risk") {
      label = "High risk";
    }
    if (label && !seen.has(label)) {
      seen.add(label);
      chips.push(
        <Badge key={label} tone="fraud">
          {label}
        </Badge>,
      );
    }
  }
  if (chips.length === 0) {
    return <span className="text-xs text-fg-muted font-mono">no specific signals</span>;
  }
  return chips;
}

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
              <span className="col-span-2 font-mono text-xs text-fg-muted flex items-center gap-2">
                {item.claim.claim_id}
                <LiveBadge at={item.decision?.decided_at ?? item.claim.submission_date} />
              </span>
              <span className="col-span-2 truncate">{item.provider.name_en}</span>
              <span className="col-span-4 flex flex-wrap items-center gap-1.5">
                {fraudSignalChips(item.decision?.flags ?? [])}
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
