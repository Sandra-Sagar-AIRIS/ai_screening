import { apiRequest } from "@/lib/api/client";
import type { PermissionModuleGroup } from "@/lib/api/types";

/** Full permission catalog from DB, grouped by module (admin UI). */
export async function getPermissionCatalog() {
  return apiRequest<PermissionModuleGroup[]>("/permissions");
}
