"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getVendorSubmissions } from "@/lib/api/vendor";
import type { Job, VendorSubmission } from "@/lib/api/types";
import { VendorStatusBadge } from "./SubmissionStatusBadge";
import { cn } from "@/lib/utils";

// ── Config ─────────────────────────────────────────────────────────────────

/** Poll interval for real-time vendor status updates (PIPE-005). */
const POLL_INTERVAL_MS = 30_000;

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ── Component ──────────────────────────────────────────────────────────────

interface VendorSubmissionTableProps {
  /** Map of job_id → job for resolving job titles. */
  jobMap?: Map<string, Job>;
  className?: string;
}

export function VendorSubmissionTable({ jobMap, className }: VendorSubmissionTableProps) {
  const [submissions, setSubmissions] = useState<VendorSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await getVendorSubmissions(200, 0);
      setSubmissions(data);
      setLastUpdated(new Date());
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Failed to load submissions.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Initial load + polling for real-time updates.
  useEffect(() => {
    void load(false);
    pollingRef.current = setInterval(() => {
      void load(true); // silent refresh — no spinner on poll
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-slate-400">
        <RefreshCw className="h-4 w-4 animate-spin mr-2" />
        <span className="text-sm">Loading submissions…</span>
      </div>
    );
  }

  if (error) {
    return <p className="py-6 text-center text-sm text-red-500">{error}</p>;
  }

  if (submissions.length === 0) {
    return (
      <div className="py-12 text-center text-slate-400">
        <p className="text-sm font-medium">No submissions yet.</p>
        <p className="mt-1 text-xs text-slate-400">
          Submit a candidate via My Jobs → Submit Candidate.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {/* Auto-refresh indicator */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-slate-400">
          {lastUpdated
            ? `Last updated ${lastUpdated.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`
            : null}
        </p>
        <button
          type="button"
          onClick={() => void load(false)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-orange-500 transition-colors"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-100 bg-white shadow-sm">
        <table className="w-full min-w-[600px]">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/60">
              {["Candidate", "Job", "Submitted", "Status", "Feedback"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-slate-500"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {submissions.map((sub) => {
              const job = jobMap?.get(sub.job_id);
              return (
                <tr
                  key={sub.id}
                  className="group transition-colors hover:bg-slate-50/50"
                >
                  {/* Candidate */}
                  <td className="px-4 py-3.5">
                    <span className="font-mono text-[11px] text-slate-400">
                      {sub.candidate_id.slice(0, 8)}…
                    </span>
                  </td>

                  {/* Job */}
                  <td className="px-4 py-3.5 text-[13px] text-slate-700">
                    {job?.title ?? (
                      <span className="font-mono text-[11px] text-slate-400">
                        {sub.job_id.slice(0, 8)}…
                      </span>
                    )}
                  </td>

                  {/* Submitted date */}
                  <td className="px-4 py-3.5 text-[12px] text-slate-500 whitespace-nowrap">
                    {fmtDate(sub.submitted_at)}
                  </td>

                  {/* Vendor status */}
                  <td className="px-4 py-3.5">
                    <VendorStatusBadge status={sub.vendor_status} />
                  </td>

                  {/* Client feedback — only when outcome is final */}
                  <td className="px-4 py-3.5 max-w-[260px]">
                    {sub.client_feedback ? (
                      <p className="text-[12px] text-slate-600 italic line-clamp-2">
                        &ldquo;{sub.client_feedback}&rdquo;
                      </p>
                    ) : (
                      <span className="text-[11px] text-slate-300">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] text-slate-400 text-center pt-1">
        Updates automatically every 30 seconds.
      </p>
    </div>
  );
}
