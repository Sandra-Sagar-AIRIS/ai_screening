import { API_BASE_URL, ApiError } from "@/lib/api/client";
import type { Pipeline } from "@/lib/api/types";

let pipelineApiState: "unknown" | "available" | "missing" = "unknown";
function setPipelineApiState(next: "unknown" | "available" | "missing") {
  pipelineApiState = next;
}

type PipelineCreatePayload = {
  candidate_id: string;
  job_id: string;
  stage?: "applied" | "screening" | "interview" | "offer" | "placed" | "rejected";
  status?: "active" | "on_hold" | "withdrawn" | "closed";
  notes?: string;
};

type PipelineUpdatePayload = {
  stage?: "applied" | "screening" | "interview" | "offer" | "placed" | "rejected";
  status?: "active" | "on_hold" | "withdrawn" | "closed";
  notes?: string;
};

export async function getPipelines(
  limit = 200,
  offset = 0,
  jobId?: string,
  candidateId?: string
) {
  if (pipelineApiState === "missing") {
    return [];
  }
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
    setPipelineApiState("missing");
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

  setPipelineApiState("available");
  return (await response.json()) as Pipeline[];
}

export async function createPipeline(payload: PipelineCreatePayload) {
  if (pipelineApiState === "missing") {
    throw new ApiError("Pipeline endpoint is unavailable.", 404);
  }
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
    if (response.status === 404 || response.status === 405) {
      setPipelineApiState("missing");
    }
    throw new ApiError("Unable to create pipeline.", response.status, detail);
  }

  setPipelineApiState("available");
  return (await response.json()) as Pipeline;
}

export async function updatePipeline(pipelineId: string, payload: PipelineUpdatePayload) {
  if (pipelineApiState === "missing") {
    throw new ApiError("Pipeline endpoint is unavailable.", 404);
  }
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
    if (response.status === 404 || response.status === 405) {
      setPipelineApiState("missing");
    }
    throw new ApiError("Unable to update pipeline.", response.status, detail);
  }

  setPipelineApiState("available");
  return (await response.json()) as Pipeline;
}
