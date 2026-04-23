import type { UserRole } from "@/lib/api/types";

export const WRITE_ROLES: UserRole[] = ["admin", "recruiter"];

export function hasAccess(role: UserRole | null, allowedRoles: UserRole[]) {
  if (!role) {
    return false;
  }
  return allowedRoles.includes(role);
}
