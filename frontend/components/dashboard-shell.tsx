"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Menu, Bell, Plus,
  LayoutDashboard, Users, Briefcase, Filter, Mail, UserCheck,
  Calendar, FileText, Settings, Shield,
  Building2, ChevronDown, ChevronLeft, ChevronRight, LogOut
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

const ICON_MAP: Record<string, React.ElementType> = {
  "Dashboard": LayoutDashboard,
  "Candidates": Users,
  "Jobs": Briefcase,
  "Pipeline": Filter,
  "My Jobs": Briefcase,
  "Clients": UserCheck,
  "Invites": Mail,
  "Users": Users,
  "Roles": Shield,
  "Settings": Settings,
  "Invite": Mail
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

  const recruitingMenu = filteredMenu.filter(i => ["Dashboard", "Candidates", "Jobs", "Pipeline", "My Jobs", "Clients", "Invites", "Invite"].includes(i.name));
  const managementMenu = filteredMenu.filter(i => ["Users", "Roles"].includes(i.name));

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
    const accessReady = permissions.length > 0 || isAdminRole(role) || !rule;
    if (!accessReady) return;
    if (!canAccessPathname(pathname, role, permissions)) {
      router.replace("/dashboard");
    }
  }, [hydrated, pathname, permissions, role, router, token]);

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  function canAccessPage() {
    if (pathname.startsWith("/candidates")) {
      return permissions.includes("candidates:read") || permissions.includes("candidates:read_own");
    }
    if (pathname.startsWith("/jobs")) {
      return permissions.includes("jobs:read");
    }
    if (pathname.startsWith("/vendor/jobs")) {
      return role === "vendor" && permissions.includes("jobs:read_limited");
    }
    if (pathname.startsWith("/pipeline")) {
      return permissions.includes("pipeline:read");
    }
    if (pathname.startsWith("/invite")) {
      return role === "admin" || permissions.includes("users:invite");
    }
    if (pathname.startsWith("/users")) {
      return role === "admin" || permissions.includes("users:invite");
    }
    if (pathname.startsWith("/roles")) {
      return role === "admin";
    }
    return true;
  }

  function canAccessNavItem(href: string) {
    if (href === "/vendor/jobs") {
      return role === "vendor" && permissions.includes("jobs:read_limited");
    }
    if (href === "/candidates") {
      return permissions.includes("candidates:read") || permissions.includes("candidates:read_own");
    }
    if (href === "/jobs") {
      return permissions.includes("jobs:read");
    }
    if (href === "/pipeline") {
      return permissions.includes("pipeline:read");
    }
    if (href === "/invite" || href === "/users") {
      return role === "admin" || permissions.includes("users:invite");
    }
    if (href === "/roles") {
      return role === "admin";
    }
    return true;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#FAFAFA] font-sans selection:bg-orange-100 selection:text-orange-900">
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm md:hidden transition-opacity"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 bg-white border-r border-slate-200/60 flex flex-col transform transition-all duration-300 ease-out md:relative shadow-[4px_0_24px_rgba(0,0,0,0.01)]",
        mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        isCollapsed ? "w-[68px]" : "w-[212px]"
      )}>
        <div className={cn("h-20 flex items-center relative", isCollapsed ? "justify-center px-0" : "px-5")}>
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-8 h-8 flex-shrink-0">
              <div className="absolute inset-0 bg-[#FF5A1F] rounded-[8px] transform rotate-45 shadow-[0_2px_4px_rgba(255,90,31,0.2)]"></div>
              <span className="relative text-white font-extrabold text-[14px] tracking-tighter">A</span>
            </div>
            {!isCollapsed && <span className="font-extrabold text-[20px] tracking-tight text-slate-900 whitespace-nowrap">AIRIS</span>}
          </div>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={cn(
              "absolute top-6 w-6 h-6 bg-slate-50 hover:bg-slate-100 rounded-full flex items-center justify-center text-slate-400 transition-colors border border-slate-200 shadow-sm z-10",
              isCollapsed ? "right-[-12px]" : "right-3"
            )}
          >
            {isCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-hide py-2">
          {renderNavGroup("Recruiting", recruitingMenu)}
          {renderNavGroup("Management", managementMenu)}
        </div>
      ) : null}
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[220px_1fr]">
          <aside className="rounded-lg border border-slate-200 bg-white p-2 h-fit">
            <nav className="space-y-1">
              {navItems.filter((item) => canAccessNavItem(item.href)).map((item) => (
                <Link
                  key={item.href}
                  className={cn(
                    "block rounded-md px-3 py-2 text-sm transition-colors",
                    pathname === item.href ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
                  )}
                  href={item.href}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            {permissions.length === 0 ? (
              <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
                No assigned permissions found. Contact your admin to request access.
              </p>
            ) : null}
          </aside>
          <main className="min-w-0">
            {!accessReady ? (
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
