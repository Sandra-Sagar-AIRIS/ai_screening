"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
import { useAuthStore } from "@/store/auth-store";

type DashboardStats = {
  candidates: number;
  jobs: number;
  pipelines: number;
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);
  const canReadCandidates = permissions.includes("candidates:read") || permissions.includes("candidates:read_own");

  useEffect(() => {
    async function loadData() {
      try {
        const [candidates, jobs, pipelines] = await Promise.all([
          canReadCandidates ? getCandidates(200, 0) : Promise.resolve([]),
          getJobs(200, 0),
          getPipelines(200, 0),
        ]);
        setStats({
          candidates: candidates.length,
          jobs: jobs.length,
          pipelines: pipelines.length,
        });
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load dashboard");
        }
      }
    }
    loadData();
  }, [canReadCandidates]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Candidates</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{stats?.candidates ?? "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{stats?.jobs ?? "-"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pipelines</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{stats?.pipelines ?? "-"}</p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
