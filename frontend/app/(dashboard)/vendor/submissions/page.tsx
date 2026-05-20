"use client";

// PIPE-005: Vendor Submission Dashboard
// Vendor sees ONLY their own submissions, with real-time polling every 30s.

import { useEffect, useState } from "react";
import { RefreshCw, Send } from "lucide-react";
import Link from "next/link";
import { getVendorJobs } from "@/lib/api/vendor";
import { useAuthStore } from "@/store/auth-store";
import { VendorSubmissionTable } from "@/components/submission/VendorSubmissionTable";
import type { Job } from "@/lib/api/types";

export default function VendorSubmissionsPage() {
  const role = useAuthStore((s) => s.role);
  const permissions = useAuthStore((s) => s.permissions);
  const canViewSubmissions =
    role === "vendor" && permissions.includes("submissions:read_own");

  const [jobMap, setJobMap] = useState<Map<string, Job>>(new Map());

  // Load job titles for resolving in the table.
  useEffect(() => {
    if (!canViewSubmissions) return;
    getVendorJobs(200, 0)
      .then((jobs) => {
        setJobMap(new Map(jobs.map((j) => [j.id, j])));
      })
      .catch(() => {
        // Non-critical — table degrades to showing raw UUIDs.
      });
  }, [canViewSubmissions]);

  if (!canViewSubmissions) {
    return (
      <section className="py-16 text-center">
        <p className="text-sm text-slate-500">
          You do not have permission to view submissions.
        </p>
      </section>
    );
  }

  return (
    <section className="min-w-0 space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">My Submissions</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Track all candidates you have submitted and their current status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/vendor/jobs"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-orange-400 hover:text-orange-600 transition-colors shadow-sm"
          >
            <Send className="h-3.5 w-3.5" />
            Submit Candidate
          </Link>
        </div>
      </div>

      {/* Status legend */}
      <div className="flex flex-wrap gap-3 text-[12px]">
        {[
          { dot: "bg-blue-500", label: "Submitted — received, awaiting review" },
          { dot: "bg-amber-400", label: "Under Review — shortlisted or interviewing" },
          { dot: "bg-emerald-500", label: "Accepted — client approved the candidate" },
          { dot: "bg-red-500", label: "Rejected — not moving forward" },
        ].map(({ dot, label }) => (
          <div key={label} className="flex items-center gap-1.5 text-slate-500">
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            {label}
          </div>
        ))}
      </div>

      {/* Table with 30s polling */}
      <VendorSubmissionTable jobMap={jobMap} />
    </section>
  );
}
