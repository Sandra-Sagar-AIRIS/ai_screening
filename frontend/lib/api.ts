import { apiRequest } from "@/lib/api/client";

export type Role = {
  id: string;
  organization_id: string;
  name: string;
  key: string;
};

export type PermissionItem = {
  code: string;
  display_name: string;
};

export type PermissionModuleGroup = {
  module: string;
  permissions: PermissionItem[];
};

export async function getRoles() {
  return apiRequest<Role[]>("/roles");
}

export async function createRole(payload: { name: string }) {
  return apiRequest<Role>("/roles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPermissions() {
  return apiRequest<PermissionModuleGroup[]>("/permissions");
}

export async function assignPermissions(roleId: string, permissions: string[]) {
  return apiRequest<string[]>(`/roles/${roleId}/permissions`, {
    method: "POST",
    body: JSON.stringify({ permissions }),
  });
}

export async function getRolePermissions(roleId: string) {
  return apiRequest<string[]>(`/roles/${roleId}/permissions`);
}
