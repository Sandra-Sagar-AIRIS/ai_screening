"use client";

import { useCallback, useRef, useState } from "react";
import { downloadAirisDocument, type AirisDocumentInput } from "@/lib/documents/documentService";

export function useDocumentDownload(input: AirisDocumentInput) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef(input);
  inputRef.current = input;

  const download = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await downloadAirisDocument(inputRef.current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to download document");
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { download, loading, error, clearError };
}
