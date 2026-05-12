import { apiRequest } from "@/lib/api/client";
import type {
  AtsPairStatusResponse,
  CandidateMatchEntry,
  CandidateMatchesResponse,
  JobMatchEntry,
  JobMatchesResponse,
} from "@/lib/api/types";

const ENRICHMENT_POLL_INITIAL_MS = 2000;   // first interval: 2 s (fast initial check)
const ENRICHMENT_POLL_MAX_INTERVAL_MS = 8000; // cap each interval at 8 s
const ENRICHMENT_POLL_BACKOFF = 1.4;          // multiply each interval by 1.4×
const ENRICHMENT_POLL_MAX_MS = 120000;

/** Returns the next poll delay using exponential backoff, capped at max. */
function nextPollMs(current: number): number {
  return Math.min(Math.round(current * ENRICHMENT_POLL_BACKOFF), ENRICHMENT_POLL_MAX_INTERVAL_MS);
}

export type AtsCandidateRescoreResponse = {
  status: string;
  candidate_id: string;
  pairs_scored: number;
  semantic_enrichment: string;
  mode: string;
};

export type AtsJobRescoreResponse = {
  job_id: string;
  match_count: number;
  generated_at: string;
  refresh_requested: boolean;
  semantic_enrichment?: string | null;
};

/** True when baseline is saved but semantic AI may still be running (or queued). */
export function atsAwaitingSemanticEnrichment(
  matches: { ats_pipeline_status?: string | null; ai_enrichment_status?: string | null }[]
): boolean {
  return matches.some((m) => {
    const p = m.ats_pipeline_status;
    const a = m.ai_enrichment_status;
    return (
      p === "ai_enriching" ||
      p === "pending" ||
      (p === "deterministic_complete" && (a === "pending" || a === "enriching"))
    );
  });
}

export async function pollCandidateMatchesUntilEnriched(
  candidateId: string,
  opts?: { onTick?: (matches: CandidateMatchEntry[]) => void }
): Promise<CandidateMatchEntry[]> {
  const deadline = Date.now() + ENRICHMENT_POLL_MAX_MS;
  let interval = ENRICHMENT_POLL_INITIAL_MS;
  let last: CandidateMatchEntry[] = [];
  while (Date.now() < deadline) {
    const result = await getCandidateMatchesAts(candidateId, { limit: 50, offset: 0 });
    last = result.matches ?? [];
    opts?.onTick?.(last);
    if (!atsAwaitingSemanticEnrichment(last)) break;
    await new Promise((r) => setTimeout(r, interval));
    interval = nextPollMs(interval);
  }
  return last;
}

export async function pollAtsPairStatusesUntilSettled(
  pairs: Array<{ candidate_id: string; job_id: string }>,
  opts?: { onTick?: (states: AtsPairStatusResponse[]) => void }
): Promise<AtsPairStatusResponse[]> {
  const deadline = Date.now() + ENRICHMENT_POLL_MAX_MS;
  let interval = ENRICHMENT_POLL_INITIAL_MS;
  let last: AtsPairStatusResponse[] = [];
  while (Date.now() < deadline) {
    last = await Promise.all(pairs.map((p) => getAtsPairStatus(p.candidate_id, p.job_id)));
    opts?.onTick?.(last);
    const inflight = last.some((s) =>
      ["queued", "pending", "parsing", "deterministic_complete", "ai_enriching"].includes(s.processing_state)
    );
    if (!inflight) break;
    await new Promise((r) => setTimeout(r, interval));
    interval = nextPollMs(interval);
  }
  return last;
}

export async function pollJobMatchesUntilEnriched(
  jobId: string,
  params: { limit: number; offset: number; sort_by?: "score_desc" | "missing_critical_asc" },
  opts?: { onTick?: (matches: JobMatchEntry[]) => void }
): Promise<JobMatchEntry[]> {
  const deadline = Date.now() + ENRICHMENT_POLL_MAX_MS;
  let interval = ENRICHMENT_POLL_INITIAL_MS;
  let last: JobMatchEntry[] = [];
  while (Date.now() < deadline) {
    const page = await getJobMatchesAts(jobId, params);
    last = page.matches ?? [];
    opts?.onTick?.(last);
    if (!atsAwaitingSemanticEnrichment(last)) break;
    await new Promise((r) => setTimeout(r, interval));
    interval = nextPollMs(interval);
  }
  return last;
}

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
  return apiRequest<AtsJobRescoreResponse>(`/jobs/${jobId}/rescore`, { method: "POST" });
}

export async function getCandidateMatchesAts(candidateId: string, params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 50),
    offset: String(params?.offset ?? 0),
  });
  return apiRequest<CandidateMatchesResponse>(`/candidates/${candidateId}/matches?${query.toString()}`);
}

export async function rescoreCandidateAts(candidateId: string) {
  return apiRequest<AtsCandidateRescoreResponse>(`/candidates/${candidateId}/rescore`, { method: "POST" });
}

export async function getAtsPairStatus(candidateId: string, jobId: string) {
  return apiRequest<AtsPairStatusResponse>(`/ats/status/${candidateId}/${jobId}`);
}
