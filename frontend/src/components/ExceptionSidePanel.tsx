import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { Badge } from "./Badge";
import { EobModal } from "./EobModal";
import { formatSAR, decisionLabel, decisionTone } from "@/lib/format";
import type { QueueItem } from "@/lib/types";

/**
 * Slide-in side panel showing a single exception's AI reasoning, policy
 * citations, similar claims (placeholder), and the four quick actions.
 *
 * Keyboard shortcuts (when focused):
 *   A — approve   D — deny   R — request info   Esc — close
 */
export function ExceptionSidePanel({
  item,
  onClose,
}: {
  item: QueueItem | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [showEob, setShowEob] = useState(false);
  const decision = item?.decision;

  const review = useMutation({
    mutationFn: async (action: "approve" | "deny") => {
      if (!item) return;
      const key = (window as unknown as { __API_KEY?: string }).__API_KEY ?? "dev-local-key-change-me";
      await api.reviewClaim(item.claim.claim_id, action, "reviewer-1", key);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["queue"] });
      onClose();
    },
  });

  useEffect(() => {
    if (!item) return;
    const handler = (e: KeyboardEvent) => {
      if (showEob) return;
      if (e.key === "Escape") onClose();
      if (e.key.toLowerCase() === "a") review.mutate("approve");
      if (e.key.toLowerCase() === "d") review.mutate("deny");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [item, showEob, onClose, review]);

  if (!item) return null;

  return (
    <>
      <div className="fixed inset-0 z-30 bg-black/40" onClick={onClose} />
      <aside
        className="fixed right-0 top-0 z-40 h-full w-full max-w-xl panel rounded-none border-l border-border-subtle p-6 overflow-y-auto animate-slide-in-right"
        role="complementary"
        aria-label="Exception details"
      >
        <header className="flex items-center justify-between gap-4 mb-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
              {item.claim.claim_type} · {item.claim.claim_id}
            </p>
            <h2 className="text-xl font-semibold mt-1">
              {item.member.full_name_en}{" "}
              <span dir="rtl" className="text-fg-secondary">
                ({item.member.full_name_ar})
              </span>
            </h2>
          </div>
          <button
            className="font-mono text-xs text-fg-secondary hover:text-fg-primary"
            onClick={onClose}
          >
            ESC
          </button>
        </header>

        <section className="grid grid-cols-2 gap-3 mb-5">
          <Stat label="Provider" value={item.provider.name_en} />
          <Stat label="City / tier" value={`${item.provider.city} · ${item.provider.network_tier}`} />
          <Stat label="Service date" value={item.claim.service_date} />
          <Stat label="Total billed" value={formatSAR(item.claim.total_billed)} />
        </section>

        {decision && (
          <section className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                AI reasoning
              </h3>
              <div className="flex items-center gap-2">
                <Badge tone={decisionTone[decision.decision_type] ?? "neutral"}>
                  {decisionLabel[decision.decision_type] ?? decision.decision_type}
                </Badge>
                <ConfidenceMeter value={decision.confidence_score} />
              </div>
            </div>
            <p className="text-sm leading-relaxed text-fg-primary">{decision.reasoning}</p>
          </section>
        )}

        {decision?.policy_citations.length ? (
          <section className="mb-5">
            <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
              Policy citations
            </h3>
            <ul className="space-y-1 text-sm">
              {decision.policy_citations.map((c) => (
                <li key={c} className="text-fg-secondary">
                  · {c}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {decision?.flags.length ? (
          <section className="mb-5">
            <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
              Flags
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {decision.flags.map((f) => (
                <Badge key={f} tone="review">
                  {f}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        <section className="mb-5">
          <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
            Line items
          </h3>
          <ul className="space-y-1 text-sm font-mono tabular-nums">
            {item.claim.line_items.map((li, i) => (
              <li key={`${li.code}-${i}`} className="flex justify-between text-fg-secondary">
                <span>
                  {li.code} · {li.description}
                </span>
                <span>
                  {li.quantity} × {li.unit_cost.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <footer className="sticky bottom-0 -mx-6 px-6 py-3 bg-bg-secondary border-t border-border-subtle">
          <div className="flex gap-2">
            <button
              className="flex-1 bg-decision-approve text-bg-primary font-medium px-3 py-2 rounded transition-colors hover:bg-accent-hover"
              onClick={() => review.mutate("approve")}
              disabled={review.isPending}
            >
              Approve <kbd className="ml-1 text-[10px] opacity-60">A</kbd>
            </button>
            <button
              className="flex-1 bg-decision-deny/90 text-fg-primary font-medium px-3 py-2 rounded hover:bg-decision-deny"
              onClick={() => review.mutate("deny")}
              disabled={review.isPending}
            >
              Deny <kbd className="ml-1 text-[10px] opacity-60">D</kbd>
            </button>
            {decision?.eob_en && decision?.eob_ar && (
              <button
                className="px-3 py-2 rounded border border-border hover:border-accent text-fg-secondary hover:text-fg-primary"
                onClick={() => setShowEob(true)}
              >
                View EOB
              </button>
            )}
          </div>
        </footer>
      </aside>

      {showEob && decision?.eob_en && decision?.eob_ar && (
        <EobModal en={decision.eob_en} ar={decision.eob_ar} onClose={() => setShowEob(false)} />
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</p>
      <p className="text-sm mt-0.5">{value}</p>
    </div>
  );
}
