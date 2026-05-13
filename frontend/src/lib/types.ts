/**
 * Wire types — mirror the backend Pydantic schemas.
 *
 * Kept hand-written rather than generated from OpenAPI so the dashboard
 * isn't blocked on an extra build step. Update in tandem with the backend
 * `schemas.py`.
 */

export type DecisionType =
  | "auto_approve"
  | "auto_approve_with_audit"
  | "auto_deny"
  | "human_review"
  | "fraud_hold";

export type ClaimStatus =
  | "received"
  | "processing"
  | "approved"
  | "denied"
  | "review"
  | "fraud_hold";

export interface LineItem {
  code: string;
  description: string;
  quantity: number;
  unit_cost: number;
}

export interface Claim {
  claim_id: string;
  claim_type: string;
  member_id: string;
  provider_id: string;
  service_date: string;
  submission_date: string;
  diagnosis_codes: string[];
  procedure_codes: string[];
  line_items: LineItem[];
  clinical_notes: string | null;
  total_billed: number;
  status: ClaimStatus;
}

export interface Decision {
  decision_id: string;
  claim_id: string;
  decision_type: DecisionType;
  decided_at: string;
  decided_by: string;
  amount_approved: number;
  amount_denied: number;
  member_responsibility: number;
  confidence_score: number;
  reasoning: string;
  policy_citations: string[];
  flags: string[];
  stage_results: Record<string, unknown>;
  eob_en: string | null;
  eob_ar: string | null;
}

export interface ClaimWithDecision {
  claim: Claim;
  decision: Decision | null;
}

export interface Member {
  member_id: string;
  full_name_en: string;
  full_name_ar: string;
  national_id: string;
  dob: string;
  gender: string;
  plan_id: string;
  policy_status: string;
  annual_limit: number;
  used_amount: number;
}

export interface Provider {
  provider_id: string;
  name_en: string;
  name_ar: string;
  provider_type: string;
  network_tier: string;
  city: string;
  fraud_risk_score: number;
}

export interface QueueItem {
  claim: Claim;
  decision: Decision | null;
  member: Member;
  provider: Provider;
  sla_age_days: number;
  priority: number;
}

export interface OverviewMetrics {
  period: string;
  total_claims: number;
  auto_adjudication_rate: number;
  avg_decision_seconds: number;
  pending_exceptions: number;
  fraud_holds: number;
  total_paid_sar: number;
}

export interface DecisionBreakdownItem {
  decision_type: DecisionType;
  count: number;
}

export interface QualityMetrics {
  override_rate: number;
  median_confidence: number;
  low_confidence_count: number;
}

export interface DemoJobState {
  job_id: string;
  kind: "run" | "reset";
  started_at: string;
  finished_at: string | null;
  total: number;
  current: number;
  error: string | null;
}

export interface RecentClaimItem {
  claim_id: string;
  submission_date: string;
  total_billed: number;
  status: ClaimStatus;
  decision_type: DecisionType | null;
  decided_at: string | null;
  confidence_score: number | null;
}

export interface ProviderInsight {
  provider_id: string;
  name_en: string;
  city: string;
  network_tier: string;
  fraud_risk_score: number;
  claim_count: number;
  total_billed: number;
}
