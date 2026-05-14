import { apiRequest } from "@/lib/api/client";
import type {
  AIScreening,
  AIScreeningCreatePayload,
  AIScreeningDetail,
  AIScreeningListItem,
  AnswerUpsertPayload,
  AIScreeningAnswer,
  RecruiterDecisionPayload,
  StartScreeningPayload,
} from "@/lib/api/types";

const BASE = "/ai-screenings";

// ── Create ────────────────────────────────────────────────────────────────────

export async function createScreening(
  payload: AIScreeningCreatePayload
): Promise<AIScreening> {
  return apiRequest<AIScreening>(BASE, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Start (create + optional pipeline stage move) ─────────────────────────────

export async function startScreening(
  payload: StartScreeningPayload
): Promise<AIScreening> {
  return apiRequest<AIScreening>(`${BASE}/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Retry (re-trigger failed background task) ─────────────────────────────────

export async function retryScreening(screeningId: string): Promise<AIScreening> {
  return apiRequest<AIScreening>(`${BASE}/${screeningId}/retry`, { method: "POST" });
}

// ── Move pipeline stage ───────────────────────────────────────────────────────

export async function movePipelineStage(
  screeningId: string,
  pipelineId: string,
  stage: string
): Promise<AIScreening> {
  return apiRequest<AIScreening>(`${BASE}/${screeningId}/move-stage`, {
    method: "POST",
    body: JSON.stringify({ pipeline_id: pipelineId, stage }),
  });
}

// ── List ──────────────────────────────────────────────────────────────────────

export async function listScreenings(params?: {
  candidate_id?: string;
  job_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<AIScreeningListItem[]> {
  const q = new URLSearchParams();
  if (params?.candidate_id) q.set("candidate_id", params.candidate_id);
  if (params?.job_id) q.set("job_id", params.job_id);
  if (params?.status) q.set("status", params.status);
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  if (params?.offset !== undefined) q.set("offset", String(params.offset));
  const qs = q.toString();
  return apiRequest<AIScreeningListItem[]>(qs ? `${BASE}?${qs}` : BASE);
}

// ── Detail ────────────────────────────────────────────────────────────────────

export async function getScreeningDetail(
  screeningId: string
): Promise<AIScreeningDetail> {
  return apiRequest<AIScreeningDetail>(`${BASE}/${screeningId}`);
}

// ── Regenerate questions ──────────────────────────────────────────────────────

export async function regenerateQuestions(
  screeningId: string
): Promise<AIScreening> {
  return apiRequest<AIScreening>(
    `${BASE}/${screeningId}/regenerate-questions`,
    { method: "POST" }
  );
}

// ── Upsert answer ─────────────────────────────────────────────────────────────

export async function upsertAnswer(
  screeningId: string,
  questionId: string,
  payload: AnswerUpsertPayload
): Promise<AIScreeningAnswer> {
  return apiRequest<AIScreeningAnswer>(
    `${BASE}/${screeningId}/answers/${questionId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    }
  );
}

// ── Trigger evaluation ────────────────────────────────────────────────────────

export async function triggerEvaluation(
  screeningId: string
): Promise<AIScreening> {
  return apiRequest<AIScreening>(`${BASE}/${screeningId}/evaluate`, {
    method: "POST",
  });
}

// ── Recruiter decision ────────────────────────────────────────────────────────

export async function recordDecision(
  screeningId: string,
  payload: RecruiterDecisionPayload
): Promise<AIScreening> {
  return apiRequest<AIScreening>(`${BASE}/${screeningId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Delete ────────────────────────────────────────────────────────────────────

export async function deleteScreening(screeningId: string): Promise<void> {
  await apiRequest<void>(`${BASE}/${screeningId}`, { method: "DELETE" });
}

// ── Polling helper ────────────────────────────────────────────────────────────

/**
 * Poll a screening until it exits a transient status.
 * Resolves when status is one of: questions_ready | completed | failed | cancelled.
 * Rejects after maxAttempts.
 */
export async function pollUntilSettled(
  screeningId: string,
  {
    intervalMs = 2500,
    maxAttempts = 60,
    onUpdate,
  }: {
    intervalMs?: number;
    maxAttempts?: number;
    onUpdate?: (screening: AIScreeningDetail) => void;
  } = {}
): Promise<AIScreeningDetail> {
  const TRANSIENT = new Set([
    "pending",
    "generating_questions",
    "evaluating",
  ]);

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const detail = await getScreeningDetail(screeningId);
    onUpdate?.(detail);
    if (!TRANSIENT.has(detail.status)) return detail;
    await new Promise<void>((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`Screening ${screeningId} did not settle after ${maxAttempts} polls`);
}
