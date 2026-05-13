/**
 * Small formatting helpers. Currency is SAR (no decimals for big numbers).
 */

/**
 * Parse a server-side ISO timestamp as UTC.
 *
 * The backend writes timestamps via `datetime.utcnow()` which produces a
 * naive ISO string with no timezone marker. `new Date(str)` would then
 * interpret it as LOCAL time and read every claim as N-hours stale, where
 * N is the user's UTC offset. We append 'Z' when no offset is present so
 * both sides agree on UTC.
 */
export function parseServerTime(iso: string | Date): Date {
  if (iso instanceof Date) return iso;
  return new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
}

const sarFmtFull = new Intl.NumberFormat("en-SA", {
  style: "currency",
  currency: "SAR",
  maximumFractionDigits: 2,
});
const sarFmtBig = new Intl.NumberFormat("en-SA", {
  style: "currency",
  currency: "SAR",
  maximumFractionDigits: 0,
});

export function formatSAR(amount: number): string {
  return Math.abs(amount) >= 10_000 ? sarFmtBig.format(amount) : sarFmtFull.format(amount);
}

export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

/**
 * Compact relative-time string ("3s ago", "12m ago", "2h ago", "yesterday").
 * Used everywhere — keep one source of truth.
 */
export function formatRelative(d: string | Date): string {
  const date = parseServerTime(d);
  const diffMs = Date.now() - date.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day === 1) return "yesterday";
  if (day < 7) return `${day} days ago`;
  if (day < 30) return `${Math.floor(day / 7)} weeks ago`;
  return `${Math.floor(day / 30)} months ago`;
}

// Legacy alias kept for callers that already use it.
export const formatRelativeDays = formatRelative;

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
