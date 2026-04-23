import { apiRequest } from "@/lib/api/client";
import type { Candidate } from "@/lib/api/types";

export async function getCandidates(limit = 50, offset = 0) {
  return apiRequest<Candidate[]>(`/candidates?limit=${limit}&offset=${offset}`);
}

export async function getCandidateById(candidateId: string) {
  return apiRequest<Candidate>(`/candidates/${candidateId}`);
}
