import { apiRequest, invalidateApiCache } from "@/lib/api/client";
import type { OrganizationRole, ReplaceRolePermissionsPayload } from "@/lib/api/types";

export async function listOrganizationRoles() {
  return apiRequest<OrganizationRole[]>("/roles");
}

export async function createOrganizationRole(payload: { name: string }) {
  return apiRequest<OrganizationRole>("/roles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getRolePermissionCodes(roleId: string) {
  return apiRequest<string[]>(`/roles/${roleId}/permissions`);
}

export async function replaceRolePermissions(roleId: string, payload: ReplaceRolePermissionsPayload) {
  return apiRequest<string[]>(`/roles/${roleId}/permissions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Delete a role by ID.
 * Throws ApiError with status 409 (detail.code === "ROLE_IN_USE") when the
 * role still has active users assigned — extract `detail.affected_users` for
 * the error UI.
 */
export async function deleteOrganizationRole(roleId: string): Promise<void> {
  await apiRequest<void>(`/roles/${roleId}`, { method: "DELETE" });
  // Bust the GET /roles cache so list re-fetches on next render.
  invalidateApiCache("/roles");
}
