/** AIR-38: Candidate notes — GET/POST /candidates/{id}/notes; admin soft-hide. */
import { apiRequest } from "@/lib/api/client";
import { getWorkspaceHeader } from "@/lib/api/candidates";

export type CandidateNote = {
  id: string;
  candidate_id: string;
  content: string;
  author_user_id: string | null;
  author_email: string | null;
  author_role: string | null;
  created_at: string;
  hidden: boolean;
};

export type CandidateNoteListResponse = {
  data: CandidateNote[];
  total: number;
};

export async function getCandidateNotes(
  candidateId: string,
  limit = 100,
  offset = 0
): Promise<CandidateNoteListResponse> {
  return apiRequest<CandidateNoteListResponse>(
    `/candidates/${candidateId}/notes?limit=${limit}&offset=${offset}`,
    {
      headers: { ...getWorkspaceHeader() },
      silentErrors: true,
    }
  );
}

export async function createCandidateNote(
  candidateId: string,
  content: string
): Promise<CandidateNote> {
  return apiRequest<CandidateNote>(`/candidates/${candidateId}/notes`, {
    method: "POST",
    body: JSON.stringify({ content }),
    headers: { ...getWorkspaceHeader() },
  });
}

export async function hideCandidateNote(
  candidateId: string,
  noteId: string
): Promise<CandidateNote> {
  return apiRequest<CandidateNote>(`/candidates/${candidateId}/notes/${noteId}/hide`, {
    method: "POST",
    headers: { ...getWorkspaceHeader() },
  });
}
