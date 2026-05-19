import { apiRequest } from "@/lib/api/client";

export type DashboardPipelineStages = {
  sourced: number;
  screening: number;
  interview: number;
  assessment: number;
  offer: number;
  placed: number;
};

export type DashboardRecentJob = {
  id: string;
  title: string;
  status: string;
  location: string | null;
  employment_type: string | null;
  created_at: string;
  candidate_count: number;
};

export type DashboardActivityItem = {
  id: string;
  type: "candidate_stage" | "job_created" | "placement";
  title: string;
  subtitle: string;
  timestamp: string;
};

export type DashboardSummary = {
  total_candidates: number;
  candidates_trend: number;
  active_jobs: number;
  jobs_trend: number;
  in_pipeline: number;
  pipeline_trend: number;
  placements: number;
  placements_trend: number;
  pipeline_stages: DashboardPipelineStages;
  recent_jobs: DashboardRecentJob[];
  activities: DashboardActivityItem[];
};

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>("/dashboard/summary");
}
