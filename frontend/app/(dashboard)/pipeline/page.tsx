"use client";

/**
 * Legacy /pipeline route — redirects to the unified pipeline workspace.
 * Preserved so any existing bookmarks / deep-links keep working.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PipelineLegacyRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/pipelines?view=kanban");
  }, [router]);
  return null;
}
