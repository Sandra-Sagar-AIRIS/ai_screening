"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { Job } from "@/lib/api/types";

type JobCardProps = {
  job: Job;
};

export function JobCard({ job }: JobCardProps) {
  return (
    <article className="rounded-md border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{job.title}</h3>
          <p className="text-sm text-slate-600">
            Company: {job.client_id ? `Client ${job.client_id.slice(0, 8)}` : "N/A"}
          </p>
          <p className="text-sm text-slate-600">Status: {job.status}</p>
          <p className="text-sm text-slate-600">Created: {new Date(job.created_at).toLocaleDateString()}</p>
        </div>
        <Link href={`/vendor/jobs/${job.id}/submit`}>
          <Button className="h-8 px-3 text-xs">Submit Candidate</Button>
        </Link>
      </div>
    </article>
  );
}

