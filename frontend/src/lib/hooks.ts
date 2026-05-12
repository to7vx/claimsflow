/**
 * TanStack Query hooks — one place for every server-state read in the app.
 *
 * Default behavior comes from the QueryClient in main.tsx (10s refetch,
 * 5s staleTime). Mutations live as inline `useMutation` calls in the
 * components that own them.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const useOverview = (period: "today" | "week" | "month" = "week") =>
  useQuery({
    queryKey: ["overview", period],
    queryFn: () => api.overview(period),
  });

export const useDecisionBreakdown = (period: "today" | "week" | "month" = "week") =>
  useQuery({
    queryKey: ["decisions-breakdown", period],
    queryFn: () => api.decisions(period),
  });

export const useExceptionQueue = () =>
  useQuery({ queryKey: ["queue", "exceptions"], queryFn: () => api.exceptions() });

export const useFraudQueue = () =>
  useQuery({ queryKey: ["queue", "fraud"], queryFn: () => api.fraud() });

export const useQuality = () =>
  useQuery({ queryKey: ["metrics", "quality"], queryFn: () => api.quality() });

export const useTopProviders = (metric: "volume" | "risk" = "volume") =>
  useQuery({
    queryKey: ["providers", "top", metric],
    queryFn: () => api.topProviders(metric, 10),
  });

export const useClaim = (id: string | null) =>
  useQuery({
    queryKey: ["claim", id],
    queryFn: () => api.getClaim(id as string),
    enabled: Boolean(id),
  });
