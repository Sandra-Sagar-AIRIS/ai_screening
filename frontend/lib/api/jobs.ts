import { apiRequest } from "@/lib/api/client";
import type { Job } from "@/lib/api/types";

export async function getJobs(limit = 50, offset = 0) {
  return apiRequest<Job[]>(`/jobs?limit=${limit}&offset=${offset}`);
}

export async function getJobById(jobId: string) {
  return apiRequest<Job>(`/jobs/${jobId}`);
}
