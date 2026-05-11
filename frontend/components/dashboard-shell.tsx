"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Menu,
  LayoutDashboard,
  Users,
  Briefcase,
  Filter,
  Mail,
  UserCheck,
  Settings,
  Shield,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  SIDEBAR_NAV_ITEMS,
  canAccessPathname,
  isAdminRole,
  matchesSidebarNavItem,
  navAccessRuleForPathname,
  SidebarNavItem,
} from "@/lib/dashboard-nav";
import { useAuthStore } from "@/store/auth-store";

const ICON_MAP: Record<string, LucideIcon> = {
  Dashboard: LayoutDashboard,
  Candidates: Users,
  Jobs: Briefcase,
  Pipeline: Filter,
  "My Jobs": Briefcase,
  Clients: UserCheck,
  Invites: Mail,
  Users: Users,
  Roles: Shield,
  Settings: Settings,
  Invite: Mail,
};

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const hydrated = useAuthStore((state) => state.hydrated);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const permissions = useAuthStore((state) => state.permissions);
  const hydrate = useAuthStore((state) => state.hydrate);
  const refreshPermissions = useAuthStore((state) => state.refreshPermissions);
  const clearToken = useAuthStore((state) => state.clearToken);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const filteredMenu = useMemo(
    () =>
      SIDEBAR_NAV_ITEMS.filter(
        (item) => item.showInSidebar !== false && matchesSidebarNavItem(role, permissions, item)
      ),
    [role, permissions]
  );

  const recruitingMenu = filteredMenu.filter((i) =>
    ["Dashboard", "Candidates", "Jobs", "Pipeline", "My Jobs", "Clients", "Invites", "Invite"].includes(i.name)
  );
  const managementMenu = filteredMenu.filter((i) => ["Users", "Roles"].includes(i.name));

  const accessRule = useMemo(() => navAccessRuleForPathname(pathname), [pathname]);
  const accessReady = permissions.length > 0 || isAdminRole(role) || !accessRule;
  const pageAllowed = canAccessPathname(pathname, role, permissions);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!token || permissions.length > 0) return;
    void refreshPermissions();
  }, [token, permissions.length, refreshPermissions]);

  useEffect(() => {
    if (!hydrated) return;
    if (token === null) router.replace("/login");
  }, [hydrated, router, token]);

  useEffect(() => {
    if (!hydrated) return;
    if (token && role === null) router.replace("/login");
  }, [hydrated, role, router, token]);

  useEffect(() => {
    if (!hydrated || token === null) return;
    const rule = navAccessRuleForPathname(pathname);
    const ready = permissions.length > 0 || isAdminRole(role) || !rule;
    if (!ready) return;
    if (!canAccessPathname(pathname, role, permissions)) {
      router.replace("/dashboard");
    }
  }, [hydrated, pathname, permissions, role, router, token]);

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  function renderNavGroup(title: string, items: SidebarNavItem[]) {
    if (items.length === 0) return null;
    return (
      <div className="mb-6">
        {!isCollapsed ? (
          <p className="mb-2 px-5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{title}</p>
        ) : null}
        <nav className="flex flex-col gap-0.5 px-2">
          {items.map((item) => {
            const Icon = ICON_MAP[item.name] ?? LayoutDashboard;
            const isActive =
              pathname === item.path || (item.path !== "/" && pathname.startsWith(`${item.path}/`));
            return (
              <Link
                key={item.path}
                href={item.path}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isCollapsed ? "justify-center px-2" : "",
                  isActive
                    ? "bg-orange-50 text-[#FF5A1F]"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
                title={isCollapsed ? item.name : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!isCollapsed ? <span className="truncate">{item.name}</span> : null}
              </Link>
            );
          })}
        </nav>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#FAFAFA] font-sans selection:bg-orange-100 selection:text-orange-900">
      {mobileNavOpen ? (
        <div
          className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm transition-opacity md:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex transform flex-col border-r border-slate-200/60 bg-white shadow-[4px_0_24px_rgba(0,0,0,0.01)] transition-all duration-300 ease-out md:relative",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          isCollapsed ? "w-[68px]" : "w-[212px]"
        )}
      >
        <div className={cn("relative flex h-20 items-center", isCollapsed ? "justify-center px-0" : "px-5")}>
          <div className="flex items-center gap-3">
            <div className="relative flex h-8 w-8 flex-shrink-0 items-center justify-center">
              <div className="absolute inset-0 rotate-45 rounded-[8px] bg-[#FF5A1F] shadow-[0_2px_4px_rgba(255,90,31,0.2)]" />
              <span className="relative text-[14px] font-extrabold tracking-tighter text-white">A</span>
            </div>
            {!isCollapsed ? (
              <span className="whitespace-nowrap text-[20px] font-extrabold tracking-tight text-slate-900">AIRIS</span>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={cn(
              "absolute top-6 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-400 shadow-sm transition-colors hover:bg-slate-100",
              isCollapsed ? "right-[-12px]" : "right-3"
            )}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </button>
        </div>

        <div className="scrollbar-hide flex-1 overflow-y-auto overflow-x-hidden py-2">
          {renderNavGroup("Recruiting", recruitingMenu)}
          {renderNavGroup("Management", managementMenu)}
        </div>

        <div className="border-t border-slate-200/60 p-2">
          <button
            type="button"
            onClick={onLogout}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900",
              isCollapsed ? "justify-center px-2" : ""
            )}
            title={isCollapsed ? "Log out" : undefined}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!isCollapsed ? "Log out" : null}
          </button>
        </div>
      </aside>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200/60 bg-white px-4 md:hidden">
          <Button
            type="button"
            variant="ghost"
            className="h-9 w-9 p-0"
            aria-label="Open menu"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
          <span className="font-semibold text-slate-900">AIRIS</span>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {!hydrated ? (
            <p className="text-sm text-slate-600">Loading...</p>
          ) : !accessReady ? (
            <p className="text-sm text-slate-600">Loading workspace...</p>
          ) : pageAllowed ? (
            children
          ) : (
            <p className="text-sm text-slate-500">Redirecting...</p>
          )}
        </main>
      </div>
    </div>
  );
}
