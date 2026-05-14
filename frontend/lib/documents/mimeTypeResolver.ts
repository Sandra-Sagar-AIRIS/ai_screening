/** Resolve human-readable labels and fetch hints from a stored file name (extension-based). */

export type DocumentMimeInfo = {
  extension: string;
  label: string;
  /** Broad category for UI copy */
  category: "pdf" | "word" | "text" | "unknown";
};

export function mimeInfoFromFileName(fileName: string | null | undefined): DocumentMimeInfo {
  const lower = (fileName || "").toLowerCase();
  if (lower.endsWith(".pdf")) {
    return { extension: ".pdf", label: "PDF document", category: "pdf" };
  }
  if (lower.endsWith(".docx")) {
    return { extension: ".docx", label: "Word document (DOCX)", category: "word" };
  }
  if (lower.endsWith(".doc")) {
    return { extension: ".doc", label: "Word document (DOC)", category: "word" };
  }
  if (lower.endsWith(".txt")) {
    return { extension: ".txt", label: "Plain text", category: "text" };
  }
  return { extension: "", label: "Document", category: "unknown" };
}
