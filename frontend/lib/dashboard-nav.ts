import type { Permission } from "@/lib/api/types";

/**
 * Permission codes used for sidebar visibility (must match backend RBAC strings).
 * Centralized so menu config does not scatter magic strings.
 */
export const NAV_PERMISSION_CODES = {
  CANDIDATES_READ: "candidates:read",
  CANDIDATES_READ_OWN: "candidates:read_own",
  JOBS_READ: "jobs:read",
  JOBS_READ_LIMITED: "jobs:read_limited",
  PIPELINE_READ: "pipeline:read",
  USERS_INVITE: "users:invite",
} as const;

export type SidebarNavItem = {
  name: string;
  path: string;
  /** If set, user must hold at least one of these permissions (unless `adminMayAccess` applies). */
  anyOfPermissions?: readonly string[];
  /** When true, only organization admins see this item. */
  adminOnly?: boolean;
  /** When true, admins see the item even without the listed permissions (e.g. user management). */
  adminMayAccess?: boolean;
  /** When false, used only for route access checks (not shown in the sidebar). */
  showInSidebar?: boolean;
};

export const SIDEBAR_NAV_ITEMS: readonly SidebarNavItem[] = [
  { name: "Dashboard", path: "/" },
  {
    name: "Candidates",
    path: "/candidates",
    anyOfPermissions: [NAV_PERMISSION_CODES.CANDIDATES_READ, NAV_PERMISSION_CODES.CANDIDATES_READ_OWN],
  },
  {
    name: "Jobs",
    path: "/dashboard/jobs",
    anyOfPermissions: [NAV_PERMISSION_CODES.JOBS_READ],
  },
  {
    name: "My Jobs",
    path: "/vendor/jobs",
    anyOfPermissions: [NAV_PERMISSION_CODES.JOBS_READ_LIMITED],
  },
  {
    name: "Pipeline",
    path: "/pipeline",
    anyOfPermissions: [NAV_PERMISSION_CODES.PIPELINE_READ],
  },
  {
    name: "Invite",
    path: "/invite",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
  },
  {
    name: "Invites",
    path: "/invites",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
  },
  {
    name: "Users",
    path: "/users",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
  },
  { name: "Roles", path: "/roles", adminOnly: true },
  // Same RBAC as above, for alternate URLs that still use DashboardShell
  { name: "Jobs (legacy path)", path: "/jobs", anyOfPermissions: [NAV_PERMISSION_CODES.JOBS_READ], showInSidebar: false },
  {
    name: "Users (dashboard path)",
    path: "/dashboard/users",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
    showInSidebar: false,
  },
  { name: "Roles (dashboard path)", path: "/dashboard/roles", adminOnly: true, showInSidebar: false },
  {
    name: "Invites (dashboard path)",
    path: "/dashboard/invites",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
    showInSidebar: false,
  },
  {
    name: "Invite (dashboard path)",
    path: "/dashboard/invite",
    anyOfPermissions: [NAV_PERMISSION_CODES.USERS_INVITE],
    adminMayAccess: true,
    showInSidebar: false,
  },
] as const;

function normalizeRole(role: string | null | undefined) {
  return (role ?? "").trim().toLowerCase();
}

export function isAdminRole(role: string | null | undefined) {
  return normalizeRole(role) === "admin";
}

/** Whether the user may see this sidebar entry. */
export function matchesSidebarNavItem(
  role: string | null | undefined,
  permissions: readonly Permission[],
  item: SidebarNavItem
): boolean {
  if (item.adminOnly) {
    return isAdminRole(role);
  }
  if (!item.anyOfPermissions?.length) {
    return true;
  }
  if (item.adminMayAccess && isAdminRole(role)) {
    return true;
  }
  return item.anyOfPermissions.some((code) => permissions.includes(code));
}

/**
 * Resolve which nav rule applies to a pathname (longest prefix wins; "/" is exact only).
 */
export function navAccessRuleForPathname(pathname: string): SidebarNavItem | null {
  if (pathname === "/") {
    return SIDEBAR_NAV_ITEMS.find((i) => i.path === "/") ?? null;
  }
  const candidates = SIDEBAR_NAV_ITEMS.filter((i) => i.path !== "/").sort((a, b) => b.path.length - a.path.length);
  return (
    candidates.find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`)) ?? null
  );
}

/** Whether the current user may access this route (same rules as sidebar, plus unknown routes allowed). */
export function canAccessPathname(
  pathname: string,
  role: string | null | undefined,
  permissions: readonly Permission[]
): boolean {
  const rule = navAccessRuleForPathname(pathname);
  if (!rule) {
    return true;
  }
  return matchesSidebarNavItem(role, permissions, rule);
}
