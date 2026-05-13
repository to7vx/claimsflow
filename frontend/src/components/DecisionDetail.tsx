import { clsx } from "clsx";
import { Badge } from "./Badge";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { decisionLabel, decisionTone, formatPercent, formatSAR } from "@/lib/format";
import type { Decision } from "@/lib/types";

/**
 * Structured decision card. Renders the AI verdict, the WHY paragraph,
 * a six-stage breakdown, and any policy citations — replacing the wall
 * of text that used to live inline in the side panel.
 */

const STAGE_ORDER = [
  "eligibility",
  "provider_validation",
  "medical_necessity",
  "fraud_detection",
  "cost_calculation",
] as const;

const STAGE_LABEL: Record<string, string> = {
  eligibility: "Eligibility",
  provider_validation: "Provider",
  medical_necessity: "Medical necessity",
  fraud_detection: "Fraud detection",
  cost_calculation: "Cost calculation",
  decision_router: "Decision router",
};

const FLAG_LABEL: Record<string, string> = {
  medical_necessity_concern: "Procedure may not match diagnosis",
  out_of_network: "Out-of-network provider",
  expired_license: "Provider license expired",
  excluded_diagnosis: "Diagnosis excluded by plan",
  limit_exceeded: "Above remaining annual limit",
  high_fraud_risk: "High fraud risk score",
  llm_failure: "AI reasoning unavailable",
  human_override: "Human override applied",
};

function humanFlag(flag: string): string {
  if (FLAG_LABEL[flag]) return FLAG_LABEL[flag];
  if (flag.startsWith("rate_variance:")) {
    return `Rate variance on ${flag.split(":")[1]}`;
  }
  if (flag.startsWith("fraud_signal:")) {
    const sig = flag.split(":")[1].replace(/_/g, " ");
    return `Fraud signal: ${sig}`;
  }
  // LLM free-text concerns (typically full sentences) pass through as-is.
  if (flag.length > 30 && /\s/.test(flag)) return flag;
  return flag.replace(/_/g, " ");
}

function nextStep(decisionType: string, flags: string[]): string | null {
  if (decisionType === "human_review") {
    if (flags.includes("medical_necessity_concern")) {
      return "Suggested: request clinical notes from the provider to confirm the procedure rationale.";
    }
    if (flags.some((f) => f.startsWith("rate_variance"))) {
      return "Suggested: contact provider billing to reconcile the rate variance.";
    }
    if (flags.includes("out_of_network")) {
      return "Suggested: confirm whether the member knowingly used out-of-network coverage.";
    }
  }
  if (decisionType === "fraud_hold") {
    return "Suggested: investigate the provider's recent claim pattern before paying.";
  }
  if (decisionType === "auto_deny") {
    return "Member denial letter generated. No further action required.";
  }
  return null;
}

type StageStatus = "passed" | "flagged" | "skipped";
function stageStatus(sr: StageResult | undefined): StageStatus {
  if (!sr || sr.data?.skipped) return "skipped";
  return sr.passed ? "passed" : "flagged";
}

interface StageResult {
  passed: boolean;
  flags: string[];
  data: Record<string, unknown> & { skipped?: boolean };
}

function getStages(decision: Decision): Record<string, StageResult> {
  return (decision.stage_results ?? {}) as Record<string, StageResult>;
}

function whyText(decision: Decision, stages: Record<string, StageResult>): string {
  // Prefer the medical-necessity LLM rationale when present, then fraud LLM,
  // else fall back to the composed reasoning string (cleaned).
  const mn = stages.medical_necessity?.data as { reasoning?: string } | undefined;
  const fr = stages.fraud_detection?.data as { llm_reasoning?: string | null } | undefined;
  if (mn?.reasoning && stages.medical_necessity && !stages.medical_necessity.passed) {
    return mn.reasoning;
  }
  if (fr?.llm_reasoning) return fr.llm_reasoning;
  // Strip the "Decision: X — ..." prefix from the composed reasoning.
  return decision.reasoning.replace(/^Decision:[^.]+\.\s*/, "");
}

function StageRow({
  name,
  status,
  detail,
}: {
  name: string;
  status: StageStatus;
  detail: string;
}) {
  const icon =
    status === "passed" ? "✓" : status === "flagged" ? "⚠" : "—";
  const color =
    status === "passed"
      ? "text-decision-approve"
      : status === "flagged"
      ? "text-decision-review"
      : "text-fg-muted";
  return (
    <li className="flex items-baseline gap-3 py-1.5 text-sm">
      <span className={clsx("font-mono w-4 shrink-0", color)} aria-hidden>
        {icon}
      </span>
      <span className="font-medium w-32 shrink-0 text-fg-primary">{name}</span>
      <span className={clsx("text-fg-secondary", status === "skipped" && "italic")}>
        {detail}
      </span>
    </li>
  );
}

export function DecisionDetail({ decision }: { decision: Decision }) {
  const stages = getStages(decision);

  const eligData = stages.eligibility?.data as
    | { remaining_limit?: number; reasons?: string[] }
    | undefined;
  const provData = stages.provider_validation?.data as
    | { network_tier?: string; rate_variance?: number }
    | undefined;
  const mnData = stages.medical_necessity?.data as
    | { confidence?: number; cached?: boolean; fast_path?: boolean }
    | undefined;
  const frData = stages.fraud_detection?.data as
    | { fraud_risk_score?: number; signals?: string[] }
    | undefined;
  const costData = stages.cost_calculation?.data as
    | { payable_to_provider?: number }
    | undefined;

  const stageRows: Array<{
    name: string;
    status: StageStatus;
    detail: string;
  }> = [
    {
      name: STAGE_LABEL.eligibility,
      status: stageStatus(stages.eligibility),
      detail:
        stageStatus(stages.eligibility) === "skipped"
          ? "Not evaluated"
          : `Remaining annual limit ${formatSAR(eligData?.remaining_limit ?? 0)}` +
            (eligData?.reasons?.length
              ? ` · ${eligData.reasons[0]}`
              : ""),
    },
    {
      name: STAGE_LABEL.provider_validation,
      status: stageStatus(stages.provider_validation),
      detail:
        stageStatus(stages.provider_validation) === "skipped"
          ? "Not evaluated"
          : `${provData?.network_tier ?? "unknown"} tier · rate variance ${Math.round(
              ((provData?.rate_variance ?? 1) - 1) * 100,
            )}%`,
    },
    {
      name: STAGE_LABEL.medical_necessity,
      status: stageStatus(stages.medical_necessity),
      detail:
        stageStatus(stages.medical_necessity) === "skipped"
          ? "Not evaluated"
          : `Confidence ${formatPercent(mnData?.confidence ?? 0, 0)}${
              mnData?.fast_path ? " · fast path" : mnData?.cached ? " · cached" : ""
            }`,
    },
    {
      name: STAGE_LABEL.fraud_detection,
      status: stageStatus(stages.fraud_detection),
      detail:
        stageStatus(stages.fraud_detection) === "skipped"
          ? "Not evaluated (short-circuited)"
          : `Risk score ${Math.round(frData?.fraud_risk_score ?? 0)}` +
            (frData?.signals?.length
              ? ` · ${frData.signals.map((s) => s.replace(/_/g, " ")).join(", ")}`
              : " · no signals"),
    },
    {
      name: STAGE_LABEL.cost_calculation,
      status: stageStatus(stages.cost_calculation),
      detail:
        stageStatus(stages.cost_calculation) === "skipped"
          ? "Not evaluated (short-circuited)"
          : `Payable ${formatSAR(costData?.payable_to_provider ?? 0)}`,
    },
  ];

  const why = whyText(decision, stages);
  const next = nextStep(decision.decision_type, decision.flags);

  return (
    <div className="space-y-5">
      <section>
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
          Decision
        </h3>
        <div className="flex items-center gap-3">
          <Badge tone={decisionTone[decision.decision_type] ?? "neutral"}>
            {decisionLabel[decision.decision_type] ?? decision.decision_type}
          </Badge>
          <ConfidenceMeter value={decision.confidence_score} />
        </div>
      </section>

      <section>
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
          Why
        </h3>
        <p className="text-sm leading-relaxed text-fg-primary">{why}</p>
        {next && (
          <p className="text-sm leading-relaxed text-fg-secondary mt-2 italic">{next}</p>
        )}
      </section>

      <section>
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
          Stage results
        </h3>
        <ul className="divide-y divide-border-subtle">
          {stageRows.map((row) => (
            <StageRow key={row.name} {...row} />
          ))}
        </ul>
      </section>

      {decision.flags.length > 0 && (
        <section>
          <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
            Flags
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {decision.flags.map((f) => (
              <Badge key={f} tone="review">
                {humanFlag(f)}
              </Badge>
            ))}
          </div>
        </section>
      )}

      {decision.policy_citations.length > 0 && (
        <section>
          <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted mb-2">
            Policy citations
          </h3>
          <ul className="space-y-1 text-sm">
            {decision.policy_citations.map((c) => (
              <li key={c} className="text-fg-secondary">
                • {c}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
