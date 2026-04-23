import { apiRequest } from "@/lib/api/client";
import type { Pipeline } from "@/lib/api/types";

export async function getPipelines(limit = 200, offset = 0) {
  return apiRequest<Pipeline[]>(`/pipelines?limit=${limit}&offset=${offset}`);
}
