import { API_BASE_URL, ApiError } from "@/lib/api/client";
import type { AIScreeningListItem, Candidate, Pipeline } from "@/lib/api/types";

export type PipelineBoardAtsEntry = {
  score: number;
  recommendation: string;
  recruiter_summary?: string | null;
  ai_enrichment_status?: string | null;
};

export type PipelineBoardCache = {
  pipelines: Pipeline[];
  candidates: Candidate[];
  atsByCandidateId: Record<string, PipelineBoardAtsEntry>;
  screeningsByCandidateId: Record<string, AIScreeningListItem>;
};

const PIPELINE_BOARD_CACHE_PREFIX = "airis_pipeline_board_v1:";
const PIPELINE_BOARD_CACHE_TTL_MS = 5 * 60_000;

export function readPipelineBoardCache(jobId: string): PipelineBoardCache | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(`${PIPELINE_BOARD_CACHE_PREFIX}${jobId}`);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as { savedAt: number; data: PipelineBoardCache };
    if (Date.now() - parsed.savedAt > PIPELINE_BOARD_CACHE_TTL_MS) {
      window.sessionStorage.removeItem(`${PIPELINE_BOARD_CACHE_PREFIX}${jobId}`);
      return null;
    }
    return parsed.data;
  } catch {
    return null;
  }
}

export function writePipelineBoardCache(jobId: string, data: PipelineBoardCache): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(
      `${PIPELINE_BOARD_CACHE_PREFIX}${jobId}`,
      JSON.stringify({ savedAt: Date.now(), data })
    );
  } catch {
    // Ignore quota errors.
  }
}

type PipelineCreatePayload = {
  candidate_id: string;
  job_id: string;
  stage?: "applied" | "screening" | "ai_screening" | "interview" | "offer" | "placed" | "rejected";
  status?: "active" | "on_hold" | "withdrawn" | "closed";
  notes?: string;
};

type PipelineUpdatePayload = {
  stage?: "applied" | "screening" | "ai_screening" | "interview" | "offer" | "placed" | "rejected";
  status?: "active" | "on_hold" | "withdrawn" | "closed";
  notes?: string;
};

export async function getPipelines(
  limit = 200,
  offset = 0,
  jobId?: string,
  candidateId?: string
) {
  const jobFilter = jobId ? `&job_id=${encodeURIComponent(jobId)}` : "";
  const candidateFilter = candidateId ? `&candidate_id=${encodeURIComponent(candidateId)}` : "";
  const token = typeof window !== "undefined" ? window.localStorage.getItem("airis_access_token") : null;
  const response = await fetch(
    `${API_BASE_URL}/pipelines?limit=${limit}&offset=${offset}${jobFilter}${candidateFilter}`,
    {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }
  );

  // Some running backend variants don't expose /pipelines; treat as empty list instead of noisy hard error.
  if (response.status === 404 || response.status === 405) {
    return [];
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError("Unable to load pipelines.", response.status, detail);
  }

  return (await response.json()) as Pipeline[];
}

export async function createPipeline(payload: PipelineCreatePayload) {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("airis_access_token") : null;
  const response = await fetch(`${API_BASE_URL}/pipelines`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError("Unable to create pipeline.", response.status, detail);
  }

  return (await response.json()) as Pipeline;
}

export async function updatePipeline(pipelineId: string, payload: PipelineUpdatePayload) {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("airis_access_token") : null;
  const response = await fetch(`${API_BASE_URL}/pipelines/${pipelineId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError("Unable to update pipeline.", response.status, detail);
  }

  return (await response.json()) as Pipeline;
}
