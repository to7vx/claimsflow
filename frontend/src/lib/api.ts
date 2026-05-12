/**
 * Typed API client for the ClaimsFlow backend.
 *
 * One small wrapper around fetch — we don't pull in a heavyweight client
 * because TanStack Query already handles caching and retries.
 */

import type {
  Claim,
  ClaimWithDecision,
  DecisionBreakdownItem,
  OverviewMetrics,
  ProviderInsight,
  QualityMetrics,
  QueueItem,
} from "./types";

const BASE = "/api/v1";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/healthz"),

  // Claims
  getClaim: (id: string) => request<ClaimWithDecision>(`${BASE}/claims/${id}`),
  listClaims: (params: { status?: string; page?: number; limit?: number } = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) q.set(k, String(v));
    }
    const qs = q.toString();
    return request<{ items: Claim[]; page: number; page_size: number; total: number }>(
      `${BASE}/claims${qs ? `?${qs}` : ""}`,
    );
  },
  reviewClaim: (
    id: string,
    decision: "approve" | "deny",
    reviewerId: string,
    apiKey: string,
    notes?: string,
  ) =>
    request(`${BASE}/claims/${id}/review`, {
      method: "POST",
      headers: { "X-API-Key": apiKey },
      body: JSON.stringify({ decision, reviewer_id: reviewerId, notes }),
    }),

  // Queues
  exceptions: () => request<QueueItem[]>(`${BASE}/queue/exceptions`),
  fraud: () => request<QueueItem[]>(`${BASE}/queue/fraud`),

  // Metrics
  overview: (period: "today" | "week" | "month" = "week") =>
    request<OverviewMetrics>(`${BASE}/metrics/overview?period=${period}`),
  decisions: (period: "today" | "week" | "month" = "week") =>
    request<DecisionBreakdownItem[]>(`${BASE}/metrics/decisions?period=${period}`),
  quality: () => request<QualityMetrics>(`${BASE}/metrics/quality`),

  // Providers
  topProviders: (metric: "volume" | "risk" = "volume", limit = 10) =>
    request<ProviderInsight[]>(`${BASE}/providers/top?metric=${metric}&limit=${limit}`),
};

export { ApiError };
