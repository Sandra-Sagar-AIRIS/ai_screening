"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatApiErrorForUser } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
<<<<<<< HEAD
import { NAV_PERMISSION_CODES, isAdminRole } from "@/lib/dashboard-nav";
import { createHasPermission } from "@/lib/rbac";
=======
>>>>>>> origin/main
import { useAuthStore } from "@/store/auth-store";

type SectionKey = "candidates" | "jobs" | "pipelines";

type DashboardStats = Partial<Record<SectionKey, number>>;
type SectionNotes = Partial<Record<SectionKey, string>>;

function isRecruiter(role: string | null | undefined) {
  return (role ?? "").trim().toLowerCase() === "recruiter";
}

export default function DashboardPage() {
<<<<<<< HEAD
  const role = useAuthStore((s) => s.role);
  const permissions = useAuthStore((s) => s.permissions);
  const refreshPermissions = useAuthStore((s) => s.refreshPermissions);

  const can = useMemo(() => createHasPermission(permissions), [permissions]);
  const canJobs = can(NAV_PERMISSION_CODES.JOBS_READ);
  const canCandidates =
    can(NAV_PERMISSION_CODES.CANDIDATES_READ) || can(NAV_PERMISSION_CODES.CANDIDATES_READ_OWN);
  const canPipelines = can(NAV_PERMISSION_CODES.PIPELINE_READ);
  const permissionsReady = permissions.length > 0 || isAdminRole(role);

  const [stats, setStats] = useState<DashboardStats>({});
  const [sectionNotes, setSectionNotes] = useState<SectionNotes>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refreshPermissions();
  }, [refreshPermissions]);
=======
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
>>>>>>> origin/main

  useEffect(() => {
    if (!permissionsReady) {
      return;
    }

    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setSectionNotes({});

      const tasks: { key: SectionKey; run: () => Promise<unknown[]> }[] = [];
      if (canCandidates) {
        tasks.push({ key: "candidates", run: () => getCandidates(200, 0) });
      }
      if (canJobs) {
        tasks.push({ key: "jobs", run: () => getJobs(200, 0) });
      }
      if (canPipelines) {
        tasks.push({ key: "pipelines", run: () => getPipelines(200, 0) });
      }

      const skipped: SectionNotes = {};
      if (!canCandidates) {
        skipped.candidates = "You don't have permission to view organization candidates here.";
      }
      if (!canJobs) {
        skipped.jobs = "You don't have permission to list jobs.";
      }
      if (!canPipelines) {
        skipped.pipelines = "You don't have permission to view pipelines.";
      }

      if (tasks.length === 0) {
        if (!cancelled) {
          setStats({});
          setSectionNotes(skipped);
          setLoading(false);
        }
        return;
      }

      const settled = await Promise.allSettled(tasks.map((t) => t.run()));
      if (cancelled) {
        return;
      }

      const nextStats: DashboardStats = {};
      const notes: SectionNotes = { ...skipped };

      settled.forEach((result, i) => {
        const key = tasks[i].key;
        if (result.status === "fulfilled") {
          const rows = result.value;
          nextStats[key] = Array.isArray(rows) ? rows.length : 0;
        } else {
          notes[key] = formatApiErrorForUser(result.reason);
        }
      });

      setStats(nextStats);
      setSectionNotes(notes);
      setLoading(false);
    }

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [permissionsReady, canCandidates, canJobs, canPipelines]);

  const hasAnyStat = Object.keys(stats).length > 0;
  const noPermissionForOverview = !canCandidates && !canJobs && !canPipelines;
  const triedAtLeastOne = canCandidates || canJobs || canPipelines;
  const fetchFailedCompletely = !loading && triedAtLeastOne && !hasAnyStat;
  const showLimitedBanner =
    permissionsReady && (noPermissionForOverview || fetchFailedCompletely);
  const pageLoading = !permissionsReady || loading;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        {isRecruiter(role) ? (
          <p className="text-sm text-slate-600">Overview for your hiring work.</p>
        ) : null}
      </div>

      {showLimitedBanner ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Limited access</p>
          <p className="mt-1 text-amber-800">
            Nothing on this overview is available with your current permissions. Try{" "}
            <Link href="/dashboard/jobs" className="font-medium text-amber-950 underline underline-offset-2">
              Jobs
            </Link>{" "}
            or another section from the sidebar.
          </p>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Candidates"
          value={stats.candidates}
          loading={pageLoading && canCandidates}
          note={sectionNotes.candidates}
        />
        <StatCard title="Jobs" value={stats.jobs} loading={pageLoading && canJobs} note={sectionNotes.jobs} />
        <StatCard
          title="Pipelines"
          value={stats.pipelines}
          loading={pageLoading && canPipelines}
          note={sectionNotes.pipelines}
        />
      </div>

      {isRecruiter(role) && permissionsReady && (hasAnyStat || !loading) ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Activity summaries will appear here as you move candidates and update jobs. For now, use the counts above
              and open <Link href="/dashboard/jobs">Jobs</Link> for detail.
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
  note?: string;
}) {
  const { title, value, loading, note } = props;
  const display =
    loading ? "…" : value === undefined ? "—" : value;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-3xl font-bold">{display}</p>
        {note ? <p className="text-xs text-slate-600">{note}</p> : null}
      </CardContent>
    </Card>
  );
}
