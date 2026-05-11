"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Menu, Bell, Plus, Search,
  LayoutDashboard, Users, Briefcase, Filter, Mail, UserCheck,
  Calendar, FileText, Settings, Shield,
  ChevronLeft, ChevronRight, LogOut
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
  const managementMenu = filteredMenu.filter(i => ["Users", "Roles", "Settings"].includes(i.name));

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

  const renderNavGroup = (title: string, items: SidebarNavItem[]) => {
    if (items.length === 0) return null;
    return (
      <div className="mb-6">
        {!isCollapsed && <h4 className="px-6 text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">{title}</h4>}
        <nav className="space-y-0.5 px-3">
          {items.map((item) => {
            const Icon = ICON_MAP[item.name] || LayoutDashboard;
            const isActive = pathname === item.path;
            return (
              <Link
                key={item.name}
                href={item.path}
                title={isCollapsed ? item.name : undefined}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-orange-50 text-orange-600" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                  isCollapsed && "justify-center px-0"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-orange-500" : "text-slate-400")} />
                {!isCollapsed && item.name}
              </Link>
            );
          })}
        </nav>
      </div>
    );
  };

  const rule = navAccessRuleForPathname(pathname);
  const accessReady = permissions.length > 0 || isAdminRole(role) || !rule;
  const pageAllowed = canAccessPathname(pathname, role, permissions);

  return (
    <div className="flex h-screen overflow-hidden bg-[#FAFAFA]">
      {/* Mobile Sidebar Overlay */}
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
              "absolute top-7 w-6 h-6 bg-white hover:bg-slate-50 rounded-full flex items-center justify-center text-slate-400 transition-colors border border-slate-200 shadow-sm z-10",
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

        <div className="p-4 border-t border-slate-100">
          <button 
            onClick={onLogout}
            className={cn(
              "flex items-center gap-3 px-3 py-2 text-sm font-medium text-slate-500 hover:text-red-600 w-full rounded-lg hover:bg-red-50 transition-colors",
              isCollapsed && "justify-center px-0"
            )}
          >
            <LogOut className="w-4 h-4" />
            {!isCollapsed && "Logout"}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex flex-shrink-0 items-center justify-between px-4 sm:px-6 lg:px-8 z-10">
          <div className="flex items-center flex-1 gap-4">
            <button
              className="md:hidden -ml-2 inline-flex items-center justify-center rounded-md p-2 text-slate-600 hover:bg-slate-100 transition-colors"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu className="w-5 h-5 text-slate-600" />
            </button>

            {/* Search Bar */}
            <div className="hidden sm:flex items-center relative max-w-md w-full">
              <Search className="w-4 h-4 absolute left-3 text-slate-400" />
              <input 
                type="text" 
                placeholder="Search candidates, jobs..." 
                className="w-full h-9 pl-9 pr-4 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] transition-all"
              />
            </div>
          </div>

          <div className="flex items-center gap-4 pl-4">
            <button className="relative p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-full hover:bg-slate-50">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#FF5A1F] rounded-full border-2 border-white"></span>
            </button>
            
            <div className="h-8 w-px bg-slate-200 hidden sm:block"></div>

            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-[#FF5A1F] font-bold text-sm">
                {role?.[0]?.toUpperCase() ?? "A"}
              </div>
              <div className="hidden md:flex flex-col">
                <span className="text-sm font-semibold text-slate-900 leading-tight">Admin User</span>
                <span className="text-[11px] text-slate-500 uppercase tracking-wide">{role ?? "Administrator"}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto w-full">
            {!accessReady ? (
              <p className="text-sm text-slate-600">Loading workspace...</p>
            ) : pageAllowed ? (
              children
            ) : (
              <p className="text-sm text-slate-500">Redirecting...</p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
