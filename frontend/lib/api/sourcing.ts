import { apiRequest } from "@/lib/api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

export type SourcingSessionStatus = "pending" | "running" | "complete" | "failed";
export type ResultAction = "pending" | "shortlisted" | "rejected" | "imported";

export interface SourcingSession {
  id: string;
  organization_id: string;
  job_id: string | null;
  created_by: string | null;
  status: SourcingSessionStatus;
  providers_used: string[] | null;
  total_results: number;
  error_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourcingResult {
  id: string;
  session_id: string;
  source: string;
  external_id: string | null;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  title: string | null;
  skills: string[] | null;
  ats_score: number | null;
  ats_tier: "Strong" | "Good" | "Moderate" | "Weak" | null;
  semantic_score: number | null;
  recruiter_summary: string | null;
  matched_skills: string[] | null;
  action: ResultAction;
  reject_reason: string | null;
  candidate_id: string | null;
  is_duplicate: boolean;
  created_at: string;
}

export interface PaginatedSourcingResults {
  items: SourcingResult[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SessionStatusResponse {
  session_id: string;
  status: SourcingSessionStatus;
  total_results: number;
}

export interface StartSessionRequest {
  jd_text: string;
  job_id?: string;
  providers?: string[];
  overrides?: Record<string, unknown>;
}

export interface ResultFilterParams {
  action?: ResultAction;
  source?: string;
  ats_tier?: string;
  page?: number;
  page_size?: number;
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function startSourcingSession(payload: StartSessionRequest): Promise<{ session_id: string }> {
  return apiRequest<{ session_id: string }>("/sourcing/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSourcingSessions(params?: {
  job_id?: string;
  page?: number;
  page_size?: number;
}): Promise<SourcingSession[]> {
  const qs = new URLSearchParams();
  if (params?.job_id) qs.set("job_id", params.job_id);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiRequest<SourcingSession[]>(`/sourcing/sessions${suffix}`);
}

export async function getSourcingSession(sessionId: string): Promise<SourcingSession> {
  return apiRequest<SourcingSession>(`/sourcing/sessions/${sessionId}`);
}

export async function pollSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
  return apiRequest<SessionStatusResponse>(`/sourcing/sessions/${sessionId}/status`);
}

export async function listSourcingResults(
  sessionId: string,
  filters?: ResultFilterParams,
): Promise<PaginatedSourcingResults> {
  const qs = new URLSearchParams();
  if (filters?.action) qs.set("action", filters.action);
  if (filters?.source) qs.set("source", filters.source);
  if (filters?.ats_tier) qs.set("ats_tier", filters.ats_tier);
  if (filters?.page) qs.set("page", String(filters.page));
  if (filters?.page_size) qs.set("page_size", String(filters.page_size ?? 20));
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiRequest<PaginatedSourcingResults>(`/sourcing/sessions/${sessionId}/results${suffix}`);
}

export async function updateResultAction(
  sessionId: string,
  resultId: string,
  payload: {
    action: "shortlisted" | "rejected" | "imported";
    reject_reason?: string;
    pipeline_stage_id?: string;
  },
): Promise<SourcingResult> {
  return apiRequest<SourcingResult>(`/sourcing/sessions/${sessionId}/results/${resultId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
