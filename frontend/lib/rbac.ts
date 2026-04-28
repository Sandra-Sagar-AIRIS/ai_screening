import type { Permission } from "@/lib/api/types";

export const CANDIDATES_CREATE_PERMISSION = "candidates:create";
export const JOBS_CREATE_PERMISSION = "jobs:create";
export const PIPELINE_UPDATE_PERMISSION = "pipeline:update";

export function hasPermission(permissions: Permission[], requiredPermission: string) {
  return permissions.includes(requiredPermission);
}
