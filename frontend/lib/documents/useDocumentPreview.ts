"use client";

import { useCallback, useRef, useState } from "react";
import { openAirisDocument, type AirisDocumentInput } from "@/lib/documents/documentService";

export function useDocumentPreview(input: AirisDocumentInput) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef(input);
  inputRef.current = input;

  const preview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await openAirisDocument(inputRef.current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open document");
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { preview, loading, error, clearError };
}
