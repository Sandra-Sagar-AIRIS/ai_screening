/**
 * Client-side guardrails before upload (server validates authoritatively).
 * Keep in sync with backend `app.documents.file_security`.
 */

const ALLOWED = new Set([".pdf", ".doc", ".docx", ".txt"]);
const MAX_BYTES = 15 * 1024 * 1024;

export function assertAllowedDocumentFile(file: File): void {
  const name = (file.name || "").toLowerCase();
  const ok = [...ALLOWED].some((ext) => name.endsWith(ext));
  if (!ok) {
    throw new Error(`Unsupported file type. Use ${[...ALLOWED].join(", ")}.`);
  }
  if (file.size > MAX_BYTES) {
    throw new Error("File is too large (max 15MB).");
  }
}
