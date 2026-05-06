import { ApiError, apiRequest } from "@/lib/api/client";
import { CANDIDATES_BULK_STAGE_PATH } from "@/lib/api/candidateManagementPaths";
import type { Candidate } from "@/lib/api/types";

const AIRIS_META_PREFIX = "__AIRIS_META__:";

type CandidateManagementEnvelope<T> = {
  success: boolean;
  data: T;
  error: string | null;
  details: unknown;
};

export type CandidateManagementParseResult = {
  parsed_resume_data: Record<string, unknown>;
  parse_confidence: number | null;
  ai_parse_version: string | null;
  extracted_skills: Array<{
    name: string;
    proficiency: string | null;
    years_experience: number | null;
    confidence: number | null;
    source: string | null;
  }>;
};

type CandidateManagementResumeUploadResponse = {
  candidate: CandidateManagementCandidate;
  parse_result: CandidateManagementParseResult;
};

type CandidateManagementListData = {
  candidates: CandidateManagementCandidate[];
  total_count: number;
  limit: number;
  offset: number;
};

type CandidateManagementCandidate = {
  id: string;
  org_id: string;
  workspace_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
  years_experience: number | null;
  headline: string | null;
  summary: string | null;
  stage: "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";
  job_id: string | null;
  recruiter_id: string | null;
  resume_s3_key: string | null;
  resume_file_name: string | null;
  source: "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency" | "import" | "merge";
  created_at: string;
  updated_at: string;
};

function shouldUseCandidateManagementApi(): boolean {
  return (process.env.NEXT_PUBLIC_USE_CANDIDATE_MANAGEMENT ?? "false").toLowerCase() === "true";
}

function getWorkspaceHeader(): Record<string, string> {
  if (typeof window === "undefined") {
    return {};
  }
  const orgId = window.localStorage.getItem("airis_organization_id");
  // Until workspace is explicitly modeled in frontend auth state, org ID is used as scoped workspace header.
  return orgId ? { "X-Workspace-Id": orgId } : {};
}

function mapCandidateManagementCandidate(candidate: CandidateManagementCandidate): Candidate {
  return {
    id: candidate.id,
    organization_id: candidate.org_id,
    first_name: candidate.first_name,
    last_name: candidate.last_name,
    email: candidate.email ?? "",
    phone: candidate.phone,
    location: candidate.location,
    role: candidate.headline,
    stage: candidate.stage,
    job_id: candidate.job_id,
    recruiter_id: candidate.recruiter_id,
    resume_s3_key: candidate.resume_s3_key,
    resume_file_name: candidate.resume_file_name,
    source: candidate.source,
    years_experience: candidate.years_experience,
    experience_summary: candidate.summary,
    education: null,
    notes: null,
    created_at: candidate.created_at,
    updated_at: candidate.updated_at,
  };
}

function mapLegacyCandidate(candidate: Candidate): Candidate {
  const meta = extractLegacyMeta(candidate.notes);
  return {
    ...candidate,
    role: meta.role ?? extractRoleFromNotes(candidate.notes),
    years_experience: meta.yearsExperience ?? extractYearsFromSummary(candidate.experience_summary),
    notes: meta.cleanNotes,
  };
}

type CreateCandidatePayload = {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  location?: string;
  headline?: string;
  years_experience?: number;
  summary?: string;
  source?: "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency" | "import" | "merge";
  stage?: "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";
  job_id?: string;
  resume_s3_key?: string;
  resume_file_name?: string;
  parse_confidence?: number;
  parsed_resume_data?: Record<string, unknown>;
};

type UpdateCandidatePayload = {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  headline?: string;
  years_experience?: number;
  summary?: string;
  status?: "active" | "archived" | "deleted";
  source?: "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency" | "import" | "merge";
  stage?: "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";
  job_id?: string;
};

type CandidateStageFilter =
  | "applied"
  | "screening"
  | "shortlisted"
  | "interview"
  | "offered"
  | "hired"
  | "rejected";
type CandidateSourceFilter = "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency";

type CandidateInteractionPayload = {
  interaction_type: "note" | "email" | "stage_change" | "interview" | "system";
  title?: string;
  body?: string;
  interaction_metadata?: Record<string, unknown>;
};

export type CandidateInteraction = {
  id: string;
  candidate_id: string;
  interaction_type: "note" | "email" | "stage_change" | "interview" | "system";
  title: string | null;
  body: string | null;
  metadata: Record<string, unknown> | null;
  actor_user_id: string | null;
  actor_role: string | null;
  created_at: string;
};

type BulkUploadRequestPayload = {
  files: string[];
  source?: "import";
};

type BulkUploadItemStatus = {
  id: string;
  status: "pending" | "processing" | "completed" | "failed" | "skipped_duplicate";
  original_file_name: string | null;
  resume_s3_key: string | null;
  error_message: string | null;
};

export type BulkUploadJobStatus = {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  total_items: number;
  processed_items: number;
  success_items: number;
  failed_items: number;
  skipped_items: number;
  items: BulkUploadItemStatus[];
};

type CandidateStatusFilter = "active" | "archived" | "deleted";

export async function getCandidates(
  limit = 50,
  offset = 0,
  filters?: {
    query?: string;
    location?: string;
    min_years_experience?: number;
    max_years_experience?: number;
    status?: CandidateStatusFilter;
    stage?: CandidateStageFilter;
    source?: CandidateSourceFilter;
    job_id?: string;
  }
) {
  if (shouldUseCandidateManagementApi()) {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (filters?.query) params.set("query", filters.query);
    if (filters?.location) params.set("location", filters.location);
    if (filters?.min_years_experience !== undefined) {
      params.set("min_years_experience", String(filters.min_years_experience));
    }
    if (filters?.max_years_experience !== undefined) {
      params.set("max_years_experience", String(filters.max_years_experience));
    }
    if (filters?.status) {
      params.set("status", filters.status);
    }
    if (filters?.stage) params.set("stage", filters.stage);
    if (filters?.source) params.set("source", filters.source);
    if (filters?.job_id) params.set("job_id", filters.job_id);
    const response = await apiRequest<CandidateManagementEnvelope<CandidateManagementListData>>(
      `/candidate-management/candidates?${params.toString()}`,
      {
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return response.data.candidates.map(mapCandidateManagementCandidate);
  }
  const legacy = await apiRequest<Candidate[]>(`/candidates?limit=${limit}&offset=${offset}`);
  return legacy.map(mapLegacyCandidate);
}

export async function getCandidateById(candidateId: string) {
  if (shouldUseCandidateManagementApi()) {
    const response = await apiRequest<CandidateManagementEnvelope<CandidateManagementCandidate>>(
      `/candidate-management/candidates/${candidateId}`,
      {
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return mapCandidateManagementCandidate(response.data);
  }
  const legacy = await apiRequest<Candidate>(`/candidates/${candidateId}`);
  return mapLegacyCandidate(legacy);
}

export async function createCandidate(payload: CreateCandidatePayload) {
  if (shouldUseCandidateManagementApi()) {
    const response = await apiRequest<CandidateManagementEnvelope<CandidateManagementCandidate>>(
      "/candidate-management/candidates",
      {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return mapCandidateManagementCandidate(response.data);
  }
  const legacyPayload = {
    first_name: payload.first_name,
    last_name: payload.last_name,
    email: payload.email,
    phone: payload.phone,
    location: payload.location,
    experience_summary:
      payload.years_experience !== undefined && payload.years_experience !== null
        ? `${payload.years_experience} years`
        : payload.summary,
    notes: payload.headline ? composeLegacyNotes({ role: payload.headline }) : undefined,
  };
  const created = await apiRequest<Candidate>("/candidates", {
    method: "POST",
    body: JSON.stringify(legacyPayload),
  });
  return mapLegacyCandidate(created);
}

export async function uploadResume(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const token = typeof window !== "undefined" ? window.localStorage.getItem("airis_access_token") : null;
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"}/candidate-management/candidates/upload-resume-file`,
    {
      method: "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...getWorkspaceHeader(),
      },
      body: formData,
    }
  );
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Resume upload failed");
  }
  const payload = (await response.json()) as CandidateManagementEnvelope<CandidateManagementResumeUploadResponse>;
  return {
    candidate: mapCandidateManagementCandidate(payload.data.candidate),
    parseResult: payload.data.parse_result,
  };
}

export async function uploadResumeForReview(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const token = typeof window !== "undefined" ? window.localStorage.getItem("airis_access_token") : null;
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"}/candidate-management/candidates/parse-resume-file`,
    {
      method: "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...getWorkspaceHeader(),
      },
      body: formData,
    }
  );
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Resume parse failed");
  }
  const payload = (await response.json()) as CandidateManagementEnvelope<{
    draft: {
      first_name: string;
      last_name: string;
      email: string;
      phone: string;
      location: string;
      headline: string;
      years_experience: number | null;
      summary: string;
      resume_s3_key: string;
      resume_file_name: string;
    };
    parse_result: CandidateManagementParseResult;
  }>;
  return payload.data;
}

export async function addCandidateInteraction(candidateId: string, payload: CandidateInteractionPayload) {
  return apiRequest<CandidateManagementEnvelope<{ id: string }>>(
    `/candidate-management/candidates/${candidateId}/interactions`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
}

export async function getCandidateInteractions(candidateId: string, limit = 50, offset = 0) {
  try {
    const response = await apiRequest<CandidateManagementEnvelope<CandidateInteraction[]>>(
      `/candidate-management/candidates/${candidateId}/interactions?limit=${limit}&offset=${offset}`,
      {
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return response.data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

export async function createBulkUploadJob(payload: BulkUploadRequestPayload) {
  const response = await apiRequest<CandidateManagementEnvelope<BulkUploadJobStatus>>("/candidate-management/bulk-upload", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
  return response.data;
}

export type InterviewRecord = {
  id: string;
  pipeline_id: string;
  scheduled_at: string;
  status: "scheduled" | "completed" | "cancelled" | "no_show" | "rescheduled";
  interviewer_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export async function createCandidateInterview(payload: {
  candidate_id: string;
  job_id?: string;
  scheduled_at: string;
  interviewer_name?: string;
  interview_type?: "HR" | "TECH";
  status?: "scheduled" | "completed" | "cancelled";
  feedback?: string;
  rating?: number;
}) {
  const response = await apiRequest<CandidateManagementEnvelope<InterviewRecord>>("/candidate-management/interviews", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
  return response.data;
}

export async function getCandidateInterviews(candidateId: string) {
  const response = await apiRequest<CandidateManagementEnvelope<InterviewRecord[]>>(
    `/candidate-management/candidates/${candidateId}/interviews`,
    {
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
  return response.data;
}

export async function updateCandidateInterview(
  interviewId: string,
  payload: {
    scheduled_at?: string;
    status?: "scheduled" | "completed" | "cancelled" | "rescheduled";
    interviewer_name?: string;
    notes?: string;
    interview_type?: "HR" | "TECH";
    rating?: number;
  }
) {
  const response = await apiRequest<CandidateManagementEnvelope<InterviewRecord>>(
    `/candidate-management/interviews/${interviewId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
  return response.data;
}

export async function bulkUpdateCandidateStage(payload: {
  candidate_ids: string[];
  stage: "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";
}) {
  return apiRequest<CandidateManagementEnvelope<{ updated_count: number }>>(CANDIDATES_BULK_STAGE_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
}

export async function bulkDeleteCandidates(payload: { candidate_ids: string[] }) {
  return apiRequest<CandidateManagementEnvelope<{ deleted_count: number }>>("/candidate-management/candidates/bulk/delete", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
}

export async function bulkUnarchiveCandidates(payload: { candidate_ids: string[] }) {
  return apiRequest<CandidateManagementEnvelope<{ unarchived_count: number }>>("/candidate-management/candidates/bulk/unarchive", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
}

export async function bulkHardDeleteCandidates(payload: { candidate_ids: string[] }) {
  return apiRequest<CandidateManagementEnvelope<{ deleted_count: number }>>("/candidate-management/candidates/bulk/hard-delete", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      ...getWorkspaceHeader(),
    },
  });
}

export async function bulkAssignRecruiter(payload: { candidate_ids: string[]; recruiter_id: string }) {
  return apiRequest<CandidateManagementEnvelope<{ updated_count: number }>>(
    "/candidate-management/candidates/bulk/assign-recruiter",
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
}

export async function assignCandidateRecruiter(candidateId: string, recruiterId: string) {
  const response = await apiRequest<CandidateManagementEnvelope<CandidateManagementCandidate>>(
    `/candidate-management/candidates/${candidateId}/assign-recruiter`,
    {
      method: "POST",
      body: JSON.stringify({ recruiter_id: recruiterId }),
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
  return mapCandidateManagementCandidate(response.data);
}

export async function getBulkUploadJobStatus(jobId: string) {
  const response = await apiRequest<CandidateManagementEnvelope<BulkUploadJobStatus>>(
    `/candidate-management/bulk-upload/${jobId}`,
    {
      headers: {
        ...getWorkspaceHeader(),
      },
    }
  );
  return response.data;
}

export async function uploadResumeAndCreateCandidate(file: File) {
  const payload = await uploadResume(file);
  return payload.candidate;
}

export async function deleteCandidate(candidateId: string) {
  if (shouldUseCandidateManagementApi()) {
    await apiRequest<CandidateManagementEnvelope<{ deleted: boolean; candidate_id: string }>>(
      `/candidate-management/candidates/${candidateId}`,
      {
        method: "DELETE",
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return;
  }
  await apiRequest(`/candidates/${candidateId}`, {
    method: "DELETE",
  });
}

export async function updateCandidate(candidateId: string, payload: UpdateCandidatePayload) {
  if (shouldUseCandidateManagementApi()) {
    const response = await apiRequest<CandidateManagementEnvelope<CandidateManagementCandidate>>(
      `/candidate-management/candidates/${candidateId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
        headers: {
          ...getWorkspaceHeader(),
        },
      }
    );
    return mapCandidateManagementCandidate(response.data);
  }
  const legacyPayload = {
    first_name: payload.first_name,
    last_name: payload.last_name,
    email: payload.email,
    phone: payload.phone,
    location: payload.location,
    experience_summary:
      payload.years_experience !== undefined && payload.years_experience !== null
        ? `${payload.years_experience} years`
        : payload.summary,
    notes: payload.headline ? composeLegacyNotes({ role: payload.headline }) : undefined,
  };
  const updated = await apiRequest<Candidate>(`/candidates/${candidateId}`, {
    method: "PUT",
    body: JSON.stringify(legacyPayload),
  });
  return mapLegacyCandidate(updated);
}

function extractRoleFromNotes(notes: string | null): string | null {
  if (!notes) {
    return null;
  }
  const marker = "ROLE:";
  if (!notes.startsWith(marker)) {
    return null;
  }
  const value = notes.slice(marker.length).trim();
  return value || null;
}

function extractYearsFromSummary(summary: string | null): number | null {
  if (!summary) {
    return null;
  }
  const match = summary.match(/(\d+)/);
  if (!match) {
    return null;
  }
  const years = Number.parseInt(match[1], 10);
  return Number.isNaN(years) ? null : years;
}

function composeLegacyNotes(meta: { role?: string | null }): string | undefined {
  const role = meta.role?.trim();
  if (!role) {
    return undefined;
  }
  return `${AIRIS_META_PREFIX}${JSON.stringify({ role })}`;
}

function extractLegacyMeta(notes: string | null): { role: string | null; yearsExperience: number | null; cleanNotes: string | null } {
  if (!notes) {
    return { role: null, yearsExperience: null, cleanNotes: null };
  }
  if (!notes.startsWith(AIRIS_META_PREFIX)) {
    const legacyRole = extractRoleFromNotes(notes);
    if (legacyRole) {
      return { role: legacyRole, yearsExperience: null, cleanNotes: null };
    }
    return { role: null, yearsExperience: null, cleanNotes: notes };
  }

  const raw = notes.slice(AIRIS_META_PREFIX.length).trim();
  try {
    const parsed = JSON.parse(raw) as { role?: string; years_experience?: number };
    return {
      role: parsed.role ?? null,
      yearsExperience: parsed.years_experience ?? null,
      cleanNotes: null,
    };
  } catch {
    return { role: null, yearsExperience: null, cleanNotes: notes };
  }
}
