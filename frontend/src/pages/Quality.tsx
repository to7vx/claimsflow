import { useQuality } from "@/lib/hooks";
import { HeroMetric } from "@/components/HeroMetric";
import { SkeletonRows } from "@/components/Skeleton";
import { formatPercent } from "@/lib/format";

export default function Quality() {
  const { data, isLoading } = useQuality();
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">AI quality</h1>
        <p className="text-sm text-fg-secondary mt-1">
          Override rates and confidence distribution across all decisions.
        </p>
      </header>

      {isLoading || !data ? (
        <SkeletonRows rows={3} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <HeroMetric
            label="Override rate"
            value={formatPercent(data.override_rate)}
            sub="reviewer disagrees with AI"
          />
          <HeroMetric
            label="Median confidence"
            value={formatPercent(data.median_confidence)}
            sub="across all decisions"
          />
          <HeroMetric
            label="Low confidence (<50%)"
            value={data.low_confidence_count.toString()}
            sub={
              data.low_confidence_count === 0
                ? "none in this window — the AI is confident"
                : "decisions routed to humans"
            }
          />
        </div>
      )}

      <section className="panel p-6">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
          Audit trail
        </h2>
        <p className="text-sm text-fg-secondary">
          Every claim has a complete audit trail in the database. Each stage emits one log entry; human overrides
          emit an additional <span className="font-mono text-fg-primary">HUMAN_OVERRIDE</span> event with the
          reviewer ID. Detail view is part of the single-claim page.
        </p>
      </section>
    </div>
  );
}
