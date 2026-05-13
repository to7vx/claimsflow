import { useState } from "react";
import { useParams } from "react-router-dom";
import { useClaim } from "@/lib/hooks";
import { Skeleton } from "@/components/Skeleton";
import { EobModal } from "@/components/EobModal";
import { DecisionDetail } from "@/components/DecisionDetail";
import { formatSAR } from "@/lib/format";

export default function ClaimDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useClaim(id ?? null);
  const [showEobModal, setShowEobModal] = useState(false);

  if (isLoading) return <Skeleton className="h-64" />;
  if (!data) return <p className="text-fg-secondary">Claim not found.</p>;

  const { claim, decision } = data;
  const hasEob = Boolean(decision?.eob_en && decision?.eob_ar);

  return (
    <div className="space-y-5">
      <header>
        <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
          {claim.claim_type}
        </p>
        <h1 className="text-2xl font-semibold mt-1">{claim.claim_id}</h1>
        <p className="text-sm text-fg-secondary mt-1">
          Service date {claim.service_date} · billed {formatSAR(claim.total_billed)}
        </p>
      </header>

      {decision && (
        <section className="panel p-5">
          <DecisionDetail decision={decision} />
          <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
            <Stat label="Approved" value={formatSAR(decision.amount_approved)} />
            <Stat label="Denied" value={formatSAR(decision.amount_denied)} />
            <Stat label="Member responsibility" value={formatSAR(decision.member_responsibility)} />
          </div>
        </section>
      )}

      {hasEob && (
        <section className="panel p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
              Explanation of benefits
            </h2>
            <button
              className="text-xs font-mono uppercase tracking-wider text-accent hover:underline"
              onClick={() => setShowEobModal(true)}
            >
              Open in modal →
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
                English
              </p>
              <p className="text-sm leading-relaxed text-fg-primary whitespace-pre-wrap">
                {decision!.eob_en}
              </p>
            </div>
            <div dir="rtl" className="md:border-l md:border-border-subtle md:pl-4">
              <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2" dir="ltr">
                Arabic
              </p>
              <p className="text-sm leading-relaxed text-fg-primary whitespace-pre-wrap">
                {decision!.eob_ar}
              </p>
            </div>
          </div>
        </section>
      )}

      <section className="panel p-5">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-3">
          Line items
        </h2>
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="text-fg-muted">
              <th className="text-left py-1">Code</th>
              <th className="text-left">Description</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Unit cost</th>
            </tr>
          </thead>
          <tbody>
            {claim.line_items.map((li, i) => (
              <tr key={`${li.code}-${i}`} className="border-t border-border-subtle">
                <td className="py-1.5">{li.code}</td>
                <td>{li.description}</td>
                <td className="text-right tabular-nums">{li.quantity}</td>
                <td className="text-right tabular-nums">{li.unit_cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {showEobModal && hasEob && (
        <EobModal en={decision!.eob_en!} ar={decision!.eob_ar!} onClose={() => setShowEobModal(false)} />
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg-tertiary border border-border-subtle rounded p-3">
      <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</p>
      <p className="text-sm mt-1 font-semibold tabular-nums">{value}</p>
    </div>
  );
}
