"use client";

import Link from "next/link";
import type { JobCandidateRow } from "@/lib/api/types";

export type CandidateTableProps = {
  rows: JobCandidateRow[];
};

function sourceLabel(source?: "internal" | "vendor") {
  if (source === "internal") {
    return "Internal";
  }
  if (source === "vendor") {
    return "Vendor";
  }
  return "—";
}

export function CandidateTable({ rows }: CandidateTableProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-600">No candidates submitted to this job yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="p-3 font-medium text-slate-700">Name</th>
            <th className="p-3 font-medium text-slate-700">Email</th>
            <th className="p-3 font-medium text-slate-700">Source</th>
            <th className="p-3 font-medium text-slate-700">Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const { candidate: c } = row;
            const name = `${c.first_name} ${c.last_name}`.trim();
            return (
              <tr key={row.pipeline_id} className="border-b border-slate-100 last:border-0">
                <td className="p-3 text-slate-900">{name || "—"}</td>
                <td className="p-3 text-slate-700">{c.email}</td>
                <td className="p-3 text-slate-700">{sourceLabel(c.source_type)}</td>
                <td className="p-3">
                  <Link
                    className="text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600"
                    href={`/candidates/${c.id}`}
                  >
                    View
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
