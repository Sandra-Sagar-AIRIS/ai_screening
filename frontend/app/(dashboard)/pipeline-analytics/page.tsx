"use client";

/**
 * PIPE-007: Pipeline Analytics Dashboard
 *
 * Sections:
 *   1. Summary cards (total, placed, rejected, placement rate)
 *   2. Conversion funnel (% advancing stage-to-stage)
 *   3. Drop-off insights (rejections ranked by severity, bottleneck flagged)
 *   4. Stage duration (avg / median days per stage, slow stages highlighted)
 *
 * Filters:
 *   - Job selector (per-job or cross-job org view)
 *   - Date range (start_date / end_date, YYYY-MM-DD)
 *
 * Export: CSV download via backend-generated export endpoint.
 */

import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw, BarChart3, TrendingDown, Clock, Target } from "lucide-react";
import { getJobs } from "@/lib/api/jobs";
import { getPipelineAnalytics, downloadAnalyticsCsv } from "@/lib/api/analytics";
import type { Job, PipelineAnalytics } from "@/lib/api/types";
import { ConversionFunnelChart } from "@/components/analytics/ConversionFunnelChart";
import { StageDurationChart } from "@/components/analytics/StageDurationChart";
import { DropoffInsightsPanel } from "@/components/analytics/DropoffInsightsPanel";
import { useAuthStore } from "@/store/auth-store";

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{label}</p>
      <p className={`mt-1 text-3xl font-extrabold tracking-tight ${accent ?? "text-slate-900"}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[12px] text-slate-400">{sub}</p>}
    </div>
  );
}

// ── Section card wrapper ───────────────────────────────────────────────────────

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-50">
          <Icon className="h-4 w-4 text-[#FF5A1F]" />
        </div>
        <h2 className="text-[15px] font-bold text-slate-800">{title}</h2>
      </div>
      {children}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function PipelineAnalyticsPage() {
  const permissions = useAuthStore((s) => s.permissions);
  const canRead = permissions.includes("pipeline:read");

  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  const [analytics, setAnalytics] = useState<PipelineAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Load job list once for the job selector.
  useEffect(() => {
    if (!canRead) return;
    getJobs(200, 0)
      .then((data) => setJobs(data))
      .catch(() => {/* non-critical */});
  }, [canRead]);

  const fetchAnalytics = useCallback(async () => {
    if (!canRead) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPipelineAnalytics({
        jobId: selectedJobId || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      });
      setAnalytics(data);
      setLastRefreshed(new Date());
    } catch (err) {
      setError((err as Error).message ?? "Failed to load analytics.");
    } finally {
      setLoading(false);
    }
  }, [canRead, selectedJobId, startDate, endDate]);

  // Load on mount + whenever filters change.
  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadAnalyticsCsv({
        jobId: selectedJobId || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      });
    } catch {
      setError("Export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  if (!canRead) {
    return (
      <section className="py-16 text-center">
        <p className="text-sm text-slate-500">
          You do not have permission to view pipeline analytics.
        </p>
      </section>
    );
  }

  return (
    <section className="min-w-0 space-y-6 pb-16">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Pipeline Analytics
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Conversion rates, stage duration, and drop-off analysis across your hiring pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void fetchAnalytics()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:border-orange-300 hover:text-orange-600 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => void handleExport()}
            disabled={exporting || loading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#FF5A1F] px-3 py-1.5 text-sm font-semibold text-white hover:bg-orange-600 transition-colors shadow-sm disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
        </div>
      </div>

      {/* ── Filters ────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
        {/* Job selector */}
        <div className="min-w-[200px] flex-1 max-w-xs">
          <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Job
          </label>
          <select
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
          >
            <option value="">All Jobs (org-wide)</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title}
              </option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div>
          <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-400">
            From
          </label>
          <input
            type="date"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-400">
            To
          </label>
          <input
            type="date"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>

        {/* Clear filters */}
        {(selectedJobId || startDate || endDate) && (
          <button
            type="button"
            onClick={() => {
              setSelectedJobId("");
              setStartDate("");
              setEndDate("");
            }}
            className="text-[12px] text-slate-400 hover:text-red-500 transition-colors self-end pb-2"
          >
            Clear filters
          </button>
        )}

        {lastRefreshed && (
          <p className="ml-auto self-end text-[11px] text-slate-400 pb-2">
            Last updated {lastRefreshed.toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && !analytics && (
        <div className="py-16 text-center">
          <RefreshCw className="mx-auto h-6 w-6 animate-spin text-orange-400 mb-3" />
          <p className="text-sm text-slate-500">Loading analytics…</p>
        </div>
      )}

      {analytics && (
        <>
          {/* ── Summary cards ─────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label="Total Pipelines"
              value={analytics.total_pipelines.toLocaleString()}
              sub={
                analytics.job_id
                  ? jobs.find((j) => j.id === analytics.job_id)?.title ?? "Single job"
                  : "Org-wide"
              }
            />
            <StatCard
              label="Placed"
              value={analytics.total_placed.toLocaleString()}
              accent="text-emerald-600"
              sub="Successfully hired"
            />
            <StatCard
              label="Rejected"
              value={analytics.total_rejected.toLocaleString()}
              accent="text-red-500"
              sub="At any stage"
            />
            <StatCard
              label="Placement Rate"
              value={`${analytics.overall_placement_rate.toFixed(1)}%`}
              accent={
                analytics.overall_placement_rate >= 60
                  ? "text-emerald-600"
                  : analytics.overall_placement_rate >= 30
                  ? "text-amber-500"
                  : "text-red-500"
              }
              sub="Placed ÷ (Placed + Rejected)"
            />
          </div>

          {/* ── Conversion funnel ──────────────────────────────────────────── */}
          <Section icon={BarChart3} title="Conversion Funnel">
            <ConversionFunnelChart funnel={analytics.funnel} />
          </Section>

          {/* ── Drop-off insights ──────────────────────────────────────────── */}
          <Section icon={TrendingDown} title="Drop-Off Insights">
            {analytics.drop_off.length > 0 && (
              <p className="mb-4 text-[13px] text-slate-500">
                Stages ranked by rejection rate — the bottleneck stage is where most candidates
                exit the pipeline.
              </p>
            )}
            <DropoffInsightsPanel dropOff={analytics.drop_off} />
          </Section>

          {/* ── Stage duration ─────────────────────────────────────────────── */}
          <Section icon={Clock} title="Average Time Per Stage">
            <StageDurationChart durations={analytics.stage_durations} />
          </Section>

          {/* ── Metadata footer ────────────────────────────────────────────── */}
          <p className="text-center text-[11px] text-slate-400">
            Generated at {new Date(analytics.generated_at).toLocaleString()} ·{" "}
            {analytics.job_id ? "Filtered to selected job" : "Org-wide view"} ·{" "}
            {analytics.date_range_start || analytics.date_range_end
              ? `${analytics.date_range_start ?? "—"} → ${analytics.date_range_end ?? "—"}`
              : "All time"}
          </p>
        </>
      )}
    </section>
  );
}
