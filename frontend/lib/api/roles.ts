import { apiRequest } from "@/lib/api/client";
import type { RoleKey, RolePermissionsResponse, UpdateRolePermissionsPayload } from "@/lib/api/types";

export async function getRolePermissions() {
  return apiRequest<RolePermissionsResponse>("/roles");
}

export async function updateRolePermissions(role: RoleKey, payload: UpdateRolePermissionsPayload) {
  return apiRequest<Record<string, string[]>>(`/roles/${role}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
