"use client";

import Link from "next/link";
import type { Job } from "@/lib/api/types";

export type JobRowMetrics = {
  vendorCount: number;
  candidateCount: number;
};

export type JobTableProps = {
  jobs: Job[];
  metrics: Record<string, JobRowMetrics>;
};

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function JobTable({ jobs, metrics }: JobTableProps) {
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="p-3 font-medium text-slate-700">Job Title</th>
            <th className="p-3 font-medium text-slate-700">Status</th>
            <th className="p-3 font-medium text-slate-700">Created</th>
            <th className="p-3 font-medium text-slate-700">Vendors</th>
            <th className="p-3 font-medium text-slate-700">Candidates</th>
            <th className="p-3 font-medium text-slate-700">Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const m = metrics[job.id] ?? { vendorCount: 0, candidateCount: 0 };
            return (
              <tr key={job.id} className="border-b border-slate-100 last:border-0">
                <td className="p-3 font-medium text-slate-900">{job.title}</td>
                <td className="p-3 capitalize text-slate-700">{job.status}</td>
                <td className="p-3 text-slate-600">{formatDate(job.created_at)}</td>
                <td className="p-3 tabular-nums text-slate-700">{m.vendorCount}</td>
                <td className="p-3 tabular-nums text-slate-700">{m.candidateCount}</td>
                <td className="p-3">
                  <Link
                    className="text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600"
                    href={`/dashboard/jobs/${job.id}`}
                  >
                    View details
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
