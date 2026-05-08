import { apiRequest } from "@/lib/api/client";
import type { CandidateMatchesResponse, JobMatchesResponse } from "@/lib/api/types";

export async function getJobMatchesAts(
  jobId: string,
  params?: {
    limit?: number;
    offset?: number;
    sort_by?: "score_desc" | "missing_critical_asc";
    min_score?: number;
    recommendation?: string;
  }
) {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 50),
    offset: String(params?.offset ?? 0),
    sort_by: params?.sort_by ?? "score_desc",
  });
  if (params?.min_score !== undefined) query.set("min_score", String(params.min_score));
  if (params?.recommendation) query.set("recommendation", params.recommendation);
  return apiRequest<JobMatchesResponse>(`/jobs/${jobId}/matches?${query.toString()}`);
}

export async function rescoreJobAts(jobId: string) {
  return apiRequest(`/jobs/${jobId}/rescore`, { method: "POST" });
}

export async function getCandidateMatchesAts(candidateId: string, params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 50),
    offset: String(params?.offset ?? 0),
  });
  return apiRequest<CandidateMatchesResponse>(`/candidates/${candidateId}/matches?${query.toString()}`);
}

export async function rescoreCandidateAts(candidateId: string) {
  return apiRequest(`/candidates/${candidateId}/rescore`, { method: "POST" });
}

