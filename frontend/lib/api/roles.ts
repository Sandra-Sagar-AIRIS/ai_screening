import { apiRequest } from "@/lib/api/client";
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
