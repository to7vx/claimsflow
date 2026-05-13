import { useState } from "react";
import { useTopProviders } from "@/lib/hooks";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonRows } from "@/components/Skeleton";
import { formatSAR } from "@/lib/format";

export default function Insights() {
  const [metric, setMetric] = useState<"volume" | "risk">("volume");
  const { data, isLoading } = useTopProviders(metric);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Provider insights</h1>
          <p className="text-sm text-fg-secondary mt-1">Top 10 by {metric}.</p>
        </div>
        <div className="inline-flex bg-bg-secondary border border-border-subtle rounded overflow-hidden text-xs font-mono">
          {(["volume", "risk"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={`px-3 py-1.5 transition-colors ${
                m === metric ? "bg-accent text-bg-primary" : "text-fg-secondary hover:text-fg-primary"
              }`}
            >
              by {m}
            </button>
          ))}
        </div>
      </header>

      {isLoading ? (
        <SkeletonRows rows={8} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="No provider data"
          message="Once claims have been processed, top providers by volume and fraud risk will appear here."
        />
      ) : (
        <div className="panel divide-y divide-border-subtle">
          {data.map((p, i) => (
            <div
              key={p.provider_id}
              className="grid grid-cols-12 items-center gap-3 px-5 py-3"
            >
              <span className="col-span-1 font-mono text-fg-muted">{i + 1}</span>
              <span className="col-span-4 truncate">
                {p.name_en}
                <span className="text-fg-muted text-xs ml-2">{p.city}</span>
              </span>
              <span className="col-span-2">
                <Badge>{p.network_tier}</Badge>
              </span>
              <span className="col-span-2 font-mono tabular-nums">
                {p.claim_count} claims
              </span>
              <span className="col-span-2 font-mono tabular-nums">
                {formatSAR(p.total_billed)}
              </span>
              <span className="col-span-1 text-right">
                <Badge tone={p.fraud_risk_score >= 50 ? "fraud" : "neutral"}>
                  {p.fraud_risk_score.toFixed(0)}
                </Badge>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
