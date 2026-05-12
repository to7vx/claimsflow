import { clsx } from "clsx";

type Tone = "approve" | "deny" | "review" | "fraud" | "neutral";

const toneClass: Record<Tone, string> = {
  approve: "bg-decision-approve/15 text-decision-approve border-decision-approve/30",
  deny: "bg-decision-deny/15 text-decision-deny border-decision-deny/30",
  review: "bg-decision-review/15 text-decision-review border-decision-review/30",
  fraud: "bg-decision-fraud/15 text-decision-fraud border-decision-fraud/30",
  neutral: "bg-bg-tertiary text-fg-secondary border-border",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-mono border",
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
