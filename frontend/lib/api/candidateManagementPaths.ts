/**
 * Paths under NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000/api/v1).
 * Keeps candidate-management URLs aligned with the FastAPI mount
 * `/api/v1/candidate-management` + router paths in `app/candidate_management/paths.py`.
 */
export const CANDIDATE_MANAGEMENT_BASE = "/candidate-management" as const;

export const CANDIDATES_BULK_STAGE_PATH = `${CANDIDATE_MANAGEMENT_BASE}/candidates/bulk/stage` as const;
