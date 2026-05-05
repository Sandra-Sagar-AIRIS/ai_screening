"use client";

import { useEffect, useState } from "react";
import { JobTable, type JobRowMetrics } from "@/components/JobTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getJobs, getJobsMetrics } from "@/lib/api";
import type { Job } from "@/lib/api/types";

export default function RecruiterJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [metrics, setMetrics] = useState<Record<string, JobRowMetrics>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const jobList = await getJobs(100, 0);
        if (cancelled) {
          return;
        }
        setJobs(jobList);

        const metricsRows = await getJobsMetrics().catch(() => []);

        if (cancelled) {
          return;
        }

        const metricsByJobId = new Map(metricsRows.map((row) => [row.job_id, row]));
        const next: Record<string, JobRowMetrics> = {};
        for (const j of jobList) {
          const row = metricsByJobId.get(j.id);
          next[j.id] = {
            candidateCount: row?.candidate_count ?? 0,
            vendorCount: row?.vendor_count ?? 0,
          };
        }
        setMetrics(next);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError("Unable to load jobs.");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Jobs</h1>
      <Card>
        <CardHeader>
          <CardTitle>All jobs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? <p className="text-sm text-slate-600">Loading jobs…</p> : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {!loading && !error && jobs.length === 0 ? (
            <p className="text-sm text-slate-600">No jobs found.</p>
          ) : null}
          {!loading && !error && jobs.length > 0 ? <JobTable jobs={jobs} metrics={metrics} /> : null}
        </CardContent>
      </Card>
    </section>
  );
}
