"use client";

import { useEffect, useState, useMemo } from "react";
import { formatApiErrorForUser } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
import { useAuthStore } from "@/store/auth-store";
import {
  Users,
  Briefcase,
  Filter,
  Trophy,
  ChevronDown,
  User,
  Search,
  Calendar,
  Award,
  FileText,
  CheckCircle2,
  MoreVertical
} from "lucide-react";
import { Candidate, Job, Pipeline } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function getRelativeTimeString(date: Date | number, lang = "en-US"): string {
  const timeMs = typeof date === "number" ? date : date.getTime();
  const deltaSeconds = Math.round((timeMs - Date.now()) / 1000);
  const cutoffs = [60, 3600, 86400, 86400 * 7, 86400 * 30, 86400 * 365, Infinity];
  const units: Intl.RelativeTimeFormatUnit[] = ["second", "minute", "hour", "day", "week", "month", "year"];
  const unitIndex = cutoffs.findIndex(cutoff => cutoff > Math.abs(deltaSeconds));
  const divider = unitIndex ? cutoffs[unitIndex - 1] : 1;
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  return rtf.format(Math.floor(deltaSeconds / divider), units[unitIndex]);
}

type ActivityItem = {
  id: string;
  type: 'candidate_stage' | 'job_created' | 'pipeline_created' | 'placement';
  title: string;
  subtitle: string;
  timestamp: Date;
};

type DashboardData = {
  candidates: Candidate[];
  jobs: Job[];
  pipelines: Pipeline[];
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);

  const canReadCandidates = permissions.includes("candidates:read") || permissions.includes("candidates:read_own");
  const canReadJobs = permissions.includes("jobs:read") || permissions.includes("jobs:read_limited");
  const canReadPipelines = permissions.includes("pipeline:read");

  async function loadData(cancelledRef?: { cancelled: boolean }, isBackground = false) {
    if (!isBackground) setLoading(true);
    if (!isBackground) setError(null);
    try {
      const [candidatesRes, jobsRes, pipelinesRes] = await Promise.allSettled([
        canReadCandidates ? getCandidates(200, 0) : Promise.resolve([]),
        canReadJobs ? getJobs(200, 0) : Promise.resolve([]),
        canReadPipelines ? getPipelines(200, 0) : Promise.resolve([]),
      ]);

      if (cancelledRef?.cancelled) return;

      const candidates = candidatesRes.status === "fulfilled" ? candidatesRes.value : [];
      const jobs = jobsRes.status === "fulfilled" ? jobsRes.value : [];
      const pipelines = pipelinesRes.status === "fulfilled" ? pipelinesRes.value : [];

      setData({ candidates, jobs, pipelines });

      if (
        candidatesRes.status === "rejected" &&
        jobsRes.status === "rejected" &&
        pipelinesRes.status === "rejected"
      ) {
        setError("Unable to load dashboard.");
      }
    } catch (err: unknown) {
      if (!cancelledRef?.cancelled) {
        setError(formatApiErrorForUser(err));
      }
    } finally {
      if (!cancelledRef?.cancelled && !isBackground) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    const cancelledRef = { cancelled: false };
    void loadData(cancelledRef, false);
    const interval = window.setInterval(() => {
      void loadData(cancelledRef, true);
    }, 30000);
    return () => {
      cancelledRef.cancelled = true;
      window.clearInterval(interval);
    };
  }, [canReadCandidates, canReadJobs, canReadPipelines]);

  const stats = useMemo(() => {
    if (!data) return null;

    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const fourteenDaysAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

    const activeJobs = data.jobs.filter(j => j.status === 'open');
    const placements = data.pipelines.filter(p => p.stage === 'placed');
    const inPipeline = data.pipelines.filter(p => p.status === 'active' && p.stage !== 'placed' && p.stage !== 'rejected');

    const getTrend = (items: any[], dateField: string) => {
      const recent = items.filter(item => new Date(item[dateField]) >= sevenDaysAgo).length;
      const previous = items.filter(item => {
        const d = new Date(item[dateField]);
        return d >= fourteenDaysAgo && d < sevenDaysAgo;
      }).length;
      if (previous === 0) return recent > 0 ? 100 : 0;
      return Math.round(((recent - previous) / previous) * 100);
    };

    const candidatesTrend = getTrend(data.candidates, 'created_at');
    const jobsTrend = getTrend(data.jobs, 'created_at');
    const pipelineTrend = getTrend(data.pipelines, 'created_at');
    const placementsTrend = getTrend(placements, 'updated_at');

    const pipelineStages = {
      applied: data.pipelines.filter(p => p.stage === 'applied' && p.status === 'active').length,
      screening: data.pipelines.filter(p => p.stage === 'screening' && p.status === 'active').length,
      interview: data.pipelines.filter(p => p.stage === 'interview' && p.status === 'active').length,
      assessment: 0,
      offer: data.pipelines.filter(p => p.stage === 'offer' && p.status === 'active').length,
      placed: placements.length,
    };

    const activities: ActivityItem[] = [];

    data.pipelines.forEach(p => {
      const candidate = data.candidates.find(c => c.id === p.candidate_id);
      const job = data.jobs.find(j => j.id === p.job_id);
      if (candidate && job) {
        activities.push({
          id: `p-${p.id}`,
          type: p.stage === 'placed' ? 'placement' : 'candidate_stage',
          title: `${candidate.first_name} ${candidate.last_name} → ${p.stage.charAt(0).toUpperCase() + p.stage.slice(1)}`,
          subtitle: job.title,
          timestamp: new Date(p.updated_at),
        });
      }
    });

    data.jobs.forEach(j => {
      activities.push({
        id: `j-${j.id}`,
        type: 'job_created',
        title: `New job created`,
        subtitle: j.title,
        timestamp: new Date(j.created_at),
      });
    });

    activities.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    // Sort jobs for recent jobs table
    const recentJobsList = [...data.jobs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 3).map(job => ({
      ...job,
      candidateCount: data.pipelines.filter(p => p.job_id === job.id).length
    }));

    return {
      totalCandidates: data.candidates.length,
      candidatesTrend,
      activeJobs: activeJobs.length,
      jobsTrend,
      inPipeline: inPipeline.length,
      pipelineTrend,
      placements: placements.length,
      placementsTrend,
      pipelineStages,
      allActivities: activities,
      recentJobsList,
    };
  }, [data]);

  const showLimitedBanner = !canReadCandidates && !canReadJobs && !canReadPipelines;

  if (showLimitedBanner) {
    return (
      <section className="space-y-4">
        <div className="rounded-[24px] shadow-[0_2px_12px_rgba(0,0,0,0.03)] bg-white px-6 py-5 text-[14px] text-slate-800">
          <p className="font-semibold text-slate-900">Limited access</p>
          <p className="mt-1 text-slate-500">
            Nothing on this overview is available with your current permissions.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="pb-10 max-w-[1400px] flex flex-col gap-6 lg:flex-row">
      {error && (
        <div className="col-span-full rounded-2xl bg-red-50 px-5 py-4 text-[14px] text-red-600 font-medium">
          {error}
        </div>
      )}

      {/* Main Left Column */}
      <div className="flex-1 space-y-8 min-w-0">

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            title="Total Candidates"
            value={stats?.totalCandidates}
            trend={stats?.candidatesTrend}
            loading={loading}
          />
          <KpiCard
            title="Active Jobs"
            value={stats?.activeJobs}
            trend={stats?.jobsTrend}
            loading={loading}
          />
          <KpiCard
            title="In Pipeline"
            value={stats?.inPipeline}
            trend={stats?.pipelineTrend}
            loading={loading}
          />
          <KpiCard
            title="Placements"
            value={stats?.placements}
            trend={stats?.placementsTrend}
            loading={loading}
          />
        </div>

        {/* Hiring Pipeline */}
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[16px] font-bold text-slate-900 tracking-tight">Active Pipeline</h3>
            <span className="text-[13px] font-bold text-[#FF5A1F] hover:text-[#e04814] cursor-pointer transition-colors">View All</span>
          </div>

          <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-6 relative overflow-hidden border border-slate-100/50">
            {/* Dashed background connection line */}
            <div className="absolute top-[2.3rem] left-16 right-16 h-[1px] border-b border-dashed border-orange-200 z-0" />

            <div className="flex items-center justify-between relative z-10 w-full px-4">
              <PipelineStage
                title="Sourced"
                value={stats?.pipelineStages.applied}
                loading={loading}
              />
              <PipelineStage
                title="Screening"
                value={stats?.pipelineStages.screening}
                loading={loading}
              />
              <PipelineStage
                title="Interview"
                value={stats?.pipelineStages.interview}
                loading={loading}
                highlight
              />
              <PipelineStage
                title="Assessment"
                value={stats?.pipelineStages.assessment}
                loading={loading}
                highlight
              />
              <PipelineStage
                title="Offer"
                value={stats?.pipelineStages.offer}
                loading={loading}
              />
              <PipelineStage
                title="Placed"
                value={stats?.pipelineStages.placed}
                loading={loading}
                isSuccess
              />
            </div>
          </div>
        </div>

        {/* Recent Jobs Table */}
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[16px] font-bold text-slate-900 tracking-tight">Recent Jobs</h3>
            <span className="text-[13px] font-bold text-[#FF5A1F] hover:text-[#e04814] cursor-pointer transition-colors">View All</span>
          </div>

          <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white overflow-hidden border border-slate-100/50">
            <div className="w-full">
              <div className="grid grid-cols-12 px-5 py-3.5 border-b border-slate-100/80 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <div className="col-span-6">Job Role</div>
                <div className="col-span-2">Candidates</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-2 text-right pr-6">Created</div>
              </div>
              <div className="divide-y divide-slate-100/60">
                {loading ? (
                  <div className="flex justify-center p-6"><span className="text-[12px] text-slate-400 font-medium">Loading jobs...</span></div>
                ) : stats?.recentJobsList && stats.recentJobsList.length > 0 ? (
                  stats.recentJobsList.map(job => {
                    const isOpen = job.status === "open";
                    return (
                    <div key={job.id} className="grid grid-cols-12 px-5 py-4 items-center hover:bg-slate-50/80 transition-colors group cursor-pointer">
                      <div className="col-span-6 flex flex-col gap-1.5 pr-4">
                        <span className="text-[14px] font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors truncate">{job.title}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[12px] font-medium text-slate-500 truncate">{job.location || 'Remote'}</span>
                          {job.employment_type && (
                            <>
                              <div className="w-1 h-1 rounded-full bg-slate-300" />
                              <span className="text-[12px] font-medium text-slate-500 capitalize whitespace-nowrap">{job.employment_type.replace("_", " ")}</span>
                            </>
                          )}
                        </div>
                      </div>
                      
                      <div className="col-span-2 flex items-center gap-2 text-slate-600">
                        <Users className="w-4 h-4 text-slate-400" />
                        <span className="text-[13px] font-bold">{(job as any).candidateCount}</span>
                      </div>
                      
                      <div className="col-span-2">
                        <span className={cn(
                          "px-2.5 py-1 rounded-md text-[10px] font-bold inline-flex items-center gap-1.5 tracking-wider uppercase",
                          isOpen ? "bg-emerald-50 text-emerald-600" : 
                          job.status === "draft" ? "bg-slate-100 text-slate-500" : 
                          "bg-blue-50 text-blue-600"
                        )}>
                          <div className={cn("w-1.5 h-1.5 rounded-full", isOpen ? "bg-emerald-500" : job.status === "draft" ? "bg-slate-400" : "bg-blue-500")} />
                          {job.status}
                        </span>
                      </div>
                      
                      <div className="col-span-2 flex items-center justify-end pr-4 opacity-80 group-hover:opacity-100 transition-opacity">
                        <span className="text-[12px] font-semibold text-slate-500 whitespace-nowrap">{getRelativeTimeString(new Date(job.created_at))}</span>
                      </div>
                    </div>
                  )})
                ) : (
                  <div className="flex justify-center p-8"><span className="text-[13px] text-slate-400 font-medium">No recent jobs</span></div>
                )}
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Right Column: Activity Feed */}
      <div className="w-full lg:w-[320px] flex-shrink-0 space-y-4">
        <div className="flex items-center justify-between px-1">
          <h3 className="text-[15px] font-bold text-slate-900 tracking-tight">Activity Log</h3>
          <div className="flex items-center gap-1 text-[12px] font-bold text-slate-600">
            All Activities <ChevronDown className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 max-h-[340px] overflow-y-auto [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-slate-200 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
          {loading ? (
            <div className="flex justify-center p-6"><span className="text-[13px] text-slate-400 font-medium">Loading activity...</span></div>
          ) : stats?.allActivities && stats.allActivities.length > 0 ? (
            <div className="space-y-6 pr-2">
              {stats.allActivities.map((activity) => (
                <ActivityRow key={activity.id} activity={activity} />
              ))}
            </div>
          ) : (
            <div className="flex justify-center p-6"><span className="text-[13px] text-slate-400 font-medium">No recent activity</span></div>
          )}
        </div>
      </div>

    </section>
  );
}

function KpiCard({
  title,
  value,
  trend,
  loading,
}: {
  title: string;
  value: number | undefined;
  trend: number | undefined;
  loading: boolean;
}) {
  const display = loading ? "…" : value === undefined ? "0" : value;
  const isPositive = (trend ?? 0) >= 0;

  return (
    <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-default">
      <div className="flex items-center justify-between mb-4">
        <p className="text-[13px] font-semibold text-slate-600 group-hover:text-[#FF5A1F] transition-colors duration-300">{title}</p>
      </div>
      <div className="flex items-center gap-2">
        <p className="text-[32px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{display}</p>
        {!loading && (
          <div className="flex items-center tracking-tight text-[12px] font-bold mt-2">
            {trend === 0 ? (
              <span className="text-slate-400">0%</span>
            ) : (
              <span className={isPositive ? "text-emerald-500" : "text-slate-400"}>
                {isPositive ? '↑' : '↓'} {Math.abs(trend ?? 0)}%
              </span>
            )}
          </div>
        )}
      </div>
      <p className="text-[12px] font-medium text-slate-400 mt-2">vs last 7 days</p>
    </div>
  );
}

function PipelineStage({
  title,
  value,
  loading,
  highlight = false,
  isSuccess = false,
}: {
  title: string;
  value: number | undefined;
  loading: boolean;
  highlight?: boolean;
  isSuccess?: boolean;
}) {
  const display = loading ? "…" : value === undefined ? "0" : value;

  return (
    <div className="flex flex-col items-center text-center relative bg-white w-20 pt-1 group cursor-default">
      <p className="text-[13px] font-semibold text-slate-600 mb-3 z-10 bg-white px-2 group-hover:text-[#FF5A1F] transition-colors duration-300">
        {title}
      </p>
      <p className="text-[28px] leading-none font-bold text-slate-900 mb-2 group-hover:text-[#FF5A1F] transition-colors duration-300">
        {display}
      </p>
      <div className="h-2 flex items-center justify-center">
        {highlight && (
          <div className="w-1.5 h-1.5 bg-purple-500 rounded-full"></div>
        )}
        {isSuccess && (
          <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></div>
        )}
      </div>
    </div>
  );
}

function ActivityRow({ activity }: { activity: ActivityItem }) {
  let icon = <div className="w-2 h-2 rounded-full bg-slate-300"></div>;

  if (activity.type === 'job_created') {
    icon = <div className="w-2 h-2 rounded-full bg-blue-500"></div>;
  } else if (activity.type === 'candidate_stage') {
    if (activity.title.includes('Assessment')) icon = <div className="w-2 h-2 rounded-full bg-pink-500"></div>;
    else if (activity.title.includes('Interview')) icon = <div className="w-2 h-2 rounded-full bg-purple-500"></div>;
    else if (activity.title.includes('Offer')) icon = <div className="w-2 h-2 rounded-full bg-blue-500"></div>;
    else icon = <div className="w-2 h-2 rounded-full bg-[#FF5A1F]"></div>;
  } else if (activity.type === 'placement') {
    icon = <div className="w-2 h-2 rounded-full bg-emerald-500"></div>;
  }

  return (
    <div className="flex items-start gap-4 cursor-default group">
      <div className="pt-1.5 flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <p className="text-[14px] font-bold text-slate-900 tracking-tight truncate leading-tight group-hover:text-[#FF5A1F] transition-colors duration-300">
          {activity.title}
        </p>
        <p className="text-[13px] font-medium text-slate-500 truncate">
          {activity.subtitle}
        </p>
        <p className="text-[12px] font-medium text-slate-400 mt-0.5">
          {getRelativeTimeString(activity.timestamp)}
        </p>
      </div>
    </div>
  );
}
