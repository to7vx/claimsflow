/**
 * Small formatting helpers. Currency is SAR (no decimals for big numbers).
 */

export function formatSAR(amount: number): string {
  if (Math.abs(amount) >= 10_000) {
    return `${Math.round(amount).toLocaleString("en-US")} SAR`;
  }
  return `${amount.toFixed(2)} SAR`;
}

export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function formatRelativeDays(d: string | Date): string {
  const date = typeof d === "string" ? new Date(d) : d;
  const diff = Math.round((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diff === 0) return "today";
  if (diff === 1) return "yesterday";
  if (diff < 7) return `${diff} days ago`;
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return `${Math.floor(diff / 30)} months ago`;
}

export const decisionLabel: Record<string, string> = {
  auto_approve: "Approved",
  auto_approve_with_audit: "Approved (audit)",
  auto_deny: "Denied",
  human_review: "Review",
  fraud_hold: "Fraud hold",
};

export const decisionTone: Record<string, "approve" | "deny" | "review" | "fraud"> = {
  auto_approve: "approve",
  auto_approve_with_audit: "approve",
  auto_deny: "deny",
  human_review: "review",
  fraud_hold: "fraud",
};
