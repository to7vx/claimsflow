import { clsx } from "clsx";
import { Link } from "react-router-dom";
import { useRecentClaims } from "@/lib/hooks";
import { Badge } from "@/components/Badge";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { Skeleton } from "@/components/Skeleton";
import { decisionLabel, decisionTone, formatRelative, parseServerTime } from "@/lib/format";
import type { RecentClaimItem } from "@/lib/types";

const LIVE_WINDOW_MS = 5 * 60 * 1000;

function isFresh(iso: string | null | undefined): boolean {
  if (!iso) return false;
  return Date.now() - parseServerTime(iso).getTime() < LIVE_WINDOW_MS;
}

export function LiveActivityPanel() {
  // Show 10 rows so a full demo_live run is visible.
  const { data, isLoading } = useRecentClaims(10);

  return (
    <section className="panel p-5">
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
            Live activity
          </h2>
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-live" aria-hidden />
        </div>
        <span className="font-mono text-[10px] text-fg-muted">refreshes every 5s</span>
      </header>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-fg-secondary text-center py-8">Waiting for activity…</p>
      ) : (
        <ul className="divide-y divide-border-subtle">
          {data.map((item) => (
            <ActivityRow key={item.claim_id} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ActivityRow({ item }: { item: RecentClaimItem }) {
  const tsIso = item.decided_at ?? item.submission_date;
  const fresh = isFresh(tsIso);
  const dt = item.decision_type;
  const tone = dt ? decisionTone[dt] : "neutral";
  const label = dt ? decisionLabel[dt] : "processing";

  return (
    <li>
      <Link
        to={`/claims/${item.claim_id}`}
        className={clsx(
          "flex items-center gap-3 py-2.5 px-2 -mx-2 rounded text-sm transition-colors",
          "hover:bg-bg-tertiary/60 focus:bg-bg-tertiary/60 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent/50 cursor-pointer",
          fresh && "animate-slide-in-right bg-accent/[0.04]",
        )}
      >
        {fresh ? (
          <span className="inline-flex items-center gap-1.5 shrink-0 w-14" title="Just submitted">
            <span className="h-2 w-2 rounded-full bg-accent animate-pulse-live" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-accent">live</span>
          </span>
        ) : (
          <span className="w-14 shrink-0" />
        )}

        <span className="font-mono text-xs text-fg-secondary tabular-nums w-20 shrink-0">
          {formatRelative(tsIso)}
        </span>

        <span className="font-mono text-xs text-fg-primary truncate flex-1">
          {item.claim_id}
        </span>

        <Badge tone={tone} className="shrink-0">
          {label}
        </Badge>

        <span className="w-32 shrink-0">
          {item.confidence_score != null ? (
            <ConfidenceMeter value={item.confidence_score} />
          ) : (
            <span className="font-mono text-[10px] text-fg-muted">—</span>
          )}
        </span>
      </Link>
    </li>
  );
}
