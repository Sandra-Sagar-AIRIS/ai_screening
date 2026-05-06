"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatApiErrorForUser } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";

type SectionKey = "candidates" | "jobs" | "pipelines";

type DashboardStats = Partial<Record<SectionKey, number>>;

function isRecruiter(role: string | null | undefined) {
  return (role ?? "").trim().toLowerCase() === "recruiter";
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const role = useAuthStore((state) => state.role);
  const permissions = useAuthStore((state) => state.permissions);
  const canReadCandidates = permissions.includes("candidates:read") || permissions.includes("candidates:read_own");
  const canReadJobs = permissions.includes("jobs:read") || permissions.includes("jobs:read_limited");
  const canReadPipelines = permissions.includes("pipeline:read");

  async function loadData(cancelledRef?: { cancelled: boolean }) {
    setLoading(true);
    setError(null);
    try {
      const [candidates, jobs, pipelines] = await Promise.allSettled([
        canReadCandidates ? getCandidates(200, 0) : Promise.resolve([]),
        canReadJobs ? getJobs(200, 0) : Promise.resolve([]),
        canReadPipelines ? getPipelines(200, 0) : Promise.resolve([]),
      ]);

      if (cancelledRef?.cancelled) return;

      setStats({
        candidates: candidates.status === "fulfilled" ? candidates.value.length : 0,
        jobs: jobs.status === "fulfilled" ? jobs.value.length : 0,
        pipelines: pipelines.status === "fulfilled" ? pipelines.value.length : 0,
      });
      if (
        candidates.status === "rejected" &&
        jobs.status === "rejected" &&
        pipelines.status === "rejected"
      ) {
        setError("Unable to load dashboard.");
      }
    } catch (err: unknown) {
      if (!cancelledRef?.cancelled) {
        setError(formatApiErrorForUser(err));
      }
    } finally {
      if (!cancelledRef?.cancelled) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    const cancelledRef = { cancelled: false };
    void loadData(cancelledRef);
    const interval = window.setInterval(() => {
      void loadData(cancelledRef);
    }, 30000);
    return () => {
      cancelledRef.cancelled = true;
      window.clearInterval(interval);
    };
  }, [canReadCandidates, canReadJobs, canReadPipelines]);

  const showLimitedBanner = !canReadCandidates && !canReadJobs && !canReadPipelines;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex items-center gap-2">
          {isRecruiter(role) ? <p className="text-sm text-slate-600">Overview for your hiring work.</p> : null}
          <Button variant="outline" className="h-8 px-3 text-xs" onClick={() => void loadData()}>
            Refresh
          </Button>
        </div>
      </div>

      {showLimitedBanner ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Limited access</p>
          <p className="mt-1 text-amber-800">
            Nothing on this overview is available with your current permissions. Try{" "}
            <Link href="/jobs" className="font-medium text-amber-950 underline underline-offset-2">
              Jobs
            </Link>{" "}
            or another section from the sidebar.
          </p>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Candidates"
          value={stats?.candidates}
          loading={loading && canReadCandidates}
        />
        <StatCard
          title="Jobs"
          value={stats?.jobs}
          loading={loading && canReadJobs}
        />
        <StatCard
          title="Pipelines"
          value={stats?.pipelines}
          loading={loading && canReadPipelines}
        />
      </div>

      {isRecruiter(role) ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Activity summaries will appear here as you move candidates and update jobs. For now, use the counts above
              and open <Link href="/jobs">Jobs</Link> for detail.
            </p>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}

function StatCard(props: {
  title: string;
  value: number | undefined;
  loading: boolean;
}) {
  const { title, value, loading } = props;
  const display =
    loading ? "…" : value === undefined ? "—" : value;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-3xl font-bold">{display}</p>
      </CardContent>
    </Card>
  );
}
