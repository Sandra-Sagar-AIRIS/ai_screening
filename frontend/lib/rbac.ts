import type { Permission } from "@/lib/api/types";

export const CANDIDATES_CREATE_PERMISSION = "candidates:create";
export const JOBS_CREATE_PERMISSION = "jobs:create";
export const JOBS_UPDATE_PERMISSION = "jobs:update";
export const PIPELINE_UPDATE_PERMISSION = "pipeline:update";

/** True if `permissions` includes the given RBAC code (same strings the API returns). */
export function hasPermission(permissions: readonly Permission[], requiredPermission: string) {
  return permissions.includes(requiredPermission);
}

/**
 * Returns `hasPermission(permission)` bound to the current user's permission list.
 * Use in components: `const can = createHasPermission(permissions); … can("jobs:read")`.
 */
export function createHasPermission(permissions: readonly Permission[]) {
  return (requiredPermission: string) => hasPermission(permissions, requiredPermission);
}
