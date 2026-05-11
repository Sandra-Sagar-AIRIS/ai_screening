/**
 * Normalize candidate UUID strings for consistent Map/Record lookups.
 * APIs and DB drivers may return UUIDs with different casing; object keys are case-sensitive.
 */
export function normalizeCandidateId(id: string | null | undefined): string {
  if (id == null || id === "") return "";
  return String(id).trim().toLowerCase();
}
