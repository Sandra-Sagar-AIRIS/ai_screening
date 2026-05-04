import { apiRequest } from "@/lib/api/client";
import type { Candidate, CandidateCreatePayload, Job, JobStatus } from "@/lib/api/types";

export async function getVendorJobs(limit = 20, offset = 0, status?: JobStatus) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) {
    params.set("status", status);
  }
  return apiRequest<Job[]>(`/vendor/jobs?${params.toString()}`);
}

export async function submitCandidate(jobId: string, payload: CandidateCreatePayload) {
  return apiRequest<Candidate>(`/jobs/${jobId}/candidates`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

