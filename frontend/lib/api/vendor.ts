import { apiRequest } from "@/lib/api/client";
import type {
  Candidate,
  CandidateCreatePayload,
  ClientFeedbackPayload,
  Job,
  JobSubmission,
  JobStatus,
  SubmissionOutcomePayload,
  VendorSubmission,
} from "@/lib/api/types";

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

// ── PIPE-005: Submission Tracking ──────────────────────────────────────────

/**
 * PIPE-005: Vendor's own submissions across all assigned jobs.
 * Returns only submissions where vendor_id == current user.
 */
export async function getVendorSubmissions(
  limit = 50,
  offset = 0,
): Promise<VendorSubmission[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiRequest<VendorSubmission[]>(`/vendor/submissions?${params.toString()}`);
}

/** PIPE-005: Recruiter/admin — set submission outcome + optional client feedback. */
export async function updateSubmissionOutcome(
  jobId: string,
  submissionId: string,
  payload: SubmissionOutcomePayload,
): Promise<JobSubmission> {
  return apiRequest<JobSubmission>(
    `/jobs/${jobId}/submissions/${submissionId}/outcome`,
    { method: "POST", body: JSON.stringify(payload) },
    0,
  );
}

/** PIPE-005: Recruiter/admin — update client feedback text. */
export async function updateSubmissionFeedback(
  jobId: string,
  submissionId: string,
  payload: ClientFeedbackPayload,
): Promise<JobSubmission> {
  return apiRequest<JobSubmission>(
    `/jobs/${jobId}/submissions/${submissionId}/feedback`,
    { method: "PATCH", body: JSON.stringify(payload) },
    0,
  );
}

/** PIPE-005: Get submissions for a specific job (recruiter view). */
export async function getJobSubmissions(
  jobId: string,
  limit = 50,
  offset = 0,
): Promise<{ data: JobSubmission[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiRequest<{ data: JobSubmission[]; total: number }>(
    `/jobs/${jobId}/submissions?${params.toString()}`,
    {},
    0,
  );
}

