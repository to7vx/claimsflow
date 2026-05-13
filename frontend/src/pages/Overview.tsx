import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useDecisionBreakdown, useOverview, useQuality } from "@/lib/hooks";
import { DemoControls } from "@/components/DemoControls";
import { HeroMetric } from "@/components/HeroMetric";
import { LiveActivityPanel } from "@/components/LiveActivityPanel";
import { Skeleton, SkeletonRows } from "@/components/Skeleton";
import { formatPercent, formatSAR, decisionLabel } from "@/lib/format";

const decisionColors: Record<string, string> = {
  auto_approve: "#46E5B5",
  auto_approve_with_audit: "#5BEEC0",
  auto_deny: "#FF6B7A",
  human_review: "#F5C04D",
  fraud_hold: "#D946EF",
};

export default function Overview() {
  const [period, setPeriod] = useState<"today" | "week" | "month">("week");
  const { data: overview, isLoading } = useOverview(period);
  const { data: breakdown } = useDecisionBreakdown(period);
  const { data: quality } = useQuality();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Operations overview</h1>
          <p className="text-sm text-fg-secondary mt-1">
            Live state of the adjudication pipeline.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <DemoControls />
          <PeriodPicker value={period} onChange={setPeriod} />
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {isLoading || !overview ? (
          <>
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </>
        ) : (
          <>
            <HeroMetric
              label="Auto-adjudication"
              value={formatPercent(overview.auto_adjudication_rate)}
              sub={`${overview.total_claims} claims this ${period}`}
              accent
            />
            <HeroMetric
              label="Avg decision"
              value={`${overview.avg_decision_seconds.toFixed(1)}s`}
              sub="across all stages"
            />
            <HeroMetric
              label="Pending reviews"
              value={overview.pending_exceptions.toString()}
              sub="exception queue"
            />
            <HeroMetric
              label="Total paid"
              value={formatSAR(overview.total_paid_sar)}
              sub={`fraud holds: ${overview.fraud_holds}`}
            />
          </>
        )}
      </div>

      <LiveActivityPanel />

      <section className="panel p-5">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-4">
          Decisions this {period}
        </h2>
        {!breakdown ? (
          <SkeletonRows rows={3} />
        ) : breakdown.length === 0 ? (
          <p className="text-sm text-fg-secondary text-center py-8">
            No decisions yet in this window. Run <code className="font-mono text-accent">claimsflow demo</code> from the CLI to seed some.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={breakdown.map((d) => ({
              name: decisionLabel[d.decision_type] ?? d.decision_type,
              key: d.decision_type,
              count: d.count,
            }))}>
              <CartesianGrid stroke="#1F2731" />
              <XAxis dataKey="name" stroke="#6F7E8C" tickLine={false} />
              <YAxis stroke="#6F7E8C" allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: "#10161D", border: "1px solid #2A3540" }}
                cursor={{ fill: "rgba(70, 229, 181, 0.05)" }}
              />
              <Legend />
              <Bar dataKey="count" fill="#46E5B5">
                {breakdown.map((d) => (
                  <Bar key={d.decision_type} dataKey="count" fill={decisionColors[d.decision_type]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      {quality && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <HeroMetric label="Human override rate" value={formatPercent(quality.override_rate)} />
          <HeroMetric label="Median confidence" value={formatPercent(quality.median_confidence)} />
          <HeroMetric label="Low-confidence decisions" value={quality.low_confidence_count.toString()} />
        </section>
      )}
    </div>
  );
}

function PeriodPicker({
  value,
  onChange,
}: {
  value: "today" | "week" | "month";
  onChange: (v: "today" | "week" | "month") => void;
}) {
  return (
    <div className="inline-flex bg-bg-secondary border border-border-subtle rounded overflow-hidden text-xs font-mono">
      {(["today", "week", "month"] as const).map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-1.5 transition-colors ${
            p === value ? "bg-accent text-bg-primary" : "text-fg-secondary hover:text-fg-primary"
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
