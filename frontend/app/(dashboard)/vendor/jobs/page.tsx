"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { getVendorJobs } from "@/lib/api/vendor";
import type { Job, JobStatus } from "@/lib/api/types";
import { JobCard } from "@/components/vendor/job-card";

const PAGE_SIZE = 10;

export default function VendorJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<JobStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getVendorJobs(PAGE_SIZE, offset, status || undefined);
        setJobs(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load vendor jobs.");
        }
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [offset, status]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">My Jobs</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-700" htmlFor="status-filter">
            Status
          </label>
          <select
            id="status-filter"
            className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
            value={status}
            onChange={(e) => {
              setOffset(0);
              setStatus(e.target.value as JobStatus | "");
            }}
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="filled">Filled</option>
          </select>
        </div>
      </div>

      {loading ? <p className="text-sm text-slate-600">Loading jobs...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {!loading && !error ? (
        <Card>
          <CardHeader>
            <CardTitle>Assigned Jobs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {jobs.length === 0 ? <p className="text-sm text-slate-600">No jobs assigned yet.</p> : null}
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}

            <div className="flex items-center justify-between border-t border-slate-100 pt-3">
              <Button
                variant="outline"
                disabled={offset === 0 || loading}
                onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
              >
                Previous
              </Button>
              <p className="text-xs text-slate-500">Offset: {offset}</p>
              <Button
                variant="outline"
                disabled={loading || jobs.length < PAGE_SIZE}
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}

