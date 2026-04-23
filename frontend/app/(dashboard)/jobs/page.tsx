"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getJobs } from "@/lib/api/jobs";
import { hasAccess, WRITE_ROLES } from "@/lib/rbac";
import type { Job } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const role = useAuthStore((state) => state.role);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getJobs(50, 0);
        setJobs(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load jobs");
        }
      }
    }
    loadData();
  }, []);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Jobs</h1>
        {hasAccess(role, WRITE_ROLES) ? <Button>Create job</Button> : null}
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <Card>
        <CardHeader>
          <CardTitle>Job List</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {jobs.map((job) => (
            <div key={job.id} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
              <div>
                <p className="font-medium">{job.title}</p>
                <p className="text-sm text-slate-600">Status: {job.status}</p>
              </div>
              <Link className="text-blue-600 hover:underline" href={`/jobs/${job.id}`}>
                View
              </Link>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}
