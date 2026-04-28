import { apiRequest } from "@/lib/api/client";
import type { OrganizationUser, UpdateUserRolePayload } from "@/lib/api/types";

export async function getUsers() {
  return apiRequest<OrganizationUser[]>("/users");
}

export async function updateUserRole(userId: string, payload: UpdateUserRolePayload) {
  return apiRequest<OrganizationUser>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
