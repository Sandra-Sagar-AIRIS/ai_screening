"use client";

import { useEffect, useState } from "react";
import { getJobSubmissions } from "@/lib/api/vendor";
import type { JobSubmission } from "@/lib/api/types";
import { SubmissionOutcomeBadge, VendorStatusBadge } from "./SubmissionStatusBadge";
import { ClientFeedbackSection } from "./ClientFeedbackSection";

interface SubmissionHistoryPanelProps {
  /** The job this candidate was submitted to. */
  jobId: string;
  /** Candidate ID for filtering (optional — if omitted all job submissions shown). */
  candidateId?: string;
  canEdit?: boolean;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function SubmissionHistoryPanel({
  jobId,
  canEdit = false,
}: SubmissionHistoryPanelProps) {
  const [submissions, setSubmissions] = useState<JobSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getJobSubmissions(jobId, 50, 0)
      .then(({ data }) => {
        if (!cancelled) {
          setSubmissions(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError((err as { message?: string })?.message ?? "Failed to load submissions.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  function handleUpdated(updated: JobSubmission) {
    setSubmissions((prev) =>
      prev.map((s) => (s.id === updated.id ? updated : s))
    );
  }

  if (loading) {
    return <p className="text-sm text-slate-400 py-4">Loading submission history…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-500 py-4">{error}</p>;
  }
  if (submissions.length === 0) {
    return <p className="text-sm text-slate-400 py-4 italic">No submissions recorded.</p>;
  }

  return (
    <ol className="relative ml-3 border-l border-slate-200 space-y-5">
      {submissions.map((sub) => (
        <li key={sub.id} className="ml-5">
          <span className="absolute -left-[7px] flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white border-2 border-orange-400" />

          <div className="flex flex-wrap items-center gap-2 mb-1">
            <p className="text-[13px] font-semibold text-slate-800">
              Submitted {fmtDate(sub.submitted_at)}
            </p>
            {sub.vendor_status && <VendorStatusBadge status={sub.vendor_status} />}
            <SubmissionOutcomeBadge outcome={sub.outcome} />
            <button
              type="button"
              onClick={() => setExpanded((e) => (e === sub.id ? null : sub.id))}
              className="ml-auto text-[11px] text-slate-400 hover:text-orange-500 transition-colors"
            >
              {expanded === sub.id ? "Hide" : "Details"}
            </button>
          </div>

          {sub.notes && (
            <p className="text-xs text-slate-500 italic mb-2">{sub.notes}</p>
          )}

          {expanded === sub.id && (
            <div className="mt-2">
              <ClientFeedbackSection
                submission={sub}
                jobId={jobId}
                canEdit={canEdit}
                onUpdated={handleUpdated}
              />
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
