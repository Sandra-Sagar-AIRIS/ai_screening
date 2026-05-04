import type { PermissionModuleGroup, Role } from "@/lib/api";

export type RoleWithPermissionCount = Role & {
  permissionsCount: number;
};

export type RoleEditorState = {
  role: Role | null;
  groups: PermissionModuleGroup[];
  selectedPermissions: string[];
};
