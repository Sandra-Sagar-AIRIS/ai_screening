"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  SIDEBAR_NAV_ITEMS,
  canAccessPathname,
  isAdminRole,
  matchesSidebarNavItem,
  navAccessRuleForPathname,
} from "@/lib/dashboard-nav";
import { useAuthStore } from "@/store/auth-store";

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

  const filteredMenu = useMemo(
    () =>
      SIDEBAR_NAV_ITEMS.filter(
        (item) => item.showInSidebar !== false && matchesSidebarNavItem(role, permissions, item)
      ),
    [role, permissions]
  );

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!token || permissions.length > 0) {
      return;
    }
    void refreshPermissions();
  }, [token, permissions.length, refreshPermissions]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    if (token === null) {
      router.replace("/login");
    }
  }, [hydrated, router, token]);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    if (token && role === null) {
      router.replace("/login");
    }
  }, [hydrated, role, router, token]);

  /** Redirect off routes the user cannot use (replaces in-page "Access restricted" card). */
  useEffect(() => {
    if (!hydrated || token === null) {
      return;
    }
    const rule = navAccessRuleForPathname(pathname);
    const accessReady = permissions.length > 0 || isAdminRole(role) || !rule;
    if (!accessReady) {
      return;
    }
    if (!canAccessPathname(pathname, role, permissions)) {
      router.replace("/");
    }
  }, [hydrated, pathname, permissions, role, router, token]);

  function onLogout() {
    clearToken();
    router.push("/login");
  }

  const rule = navAccessRuleForPathname(pathname);
  const accessReady = permissions.length > 0 || isAdminRole(role) || !rule;
  const pageAllowed = canAccessPathname(pathname, role, permissions);

  function renderNav() {
    return (
      <>
        <nav className="space-y-1">
          {filteredMenu.map((item) => {
            const active =
              item.path === "/"
                ? pathname === "/"
                : pathname === item.path || pathname.startsWith(`${item.path}/`);
            return (
              <Link
                key={item.path}
                className={cn(
                  "block rounded-md px-3 py-2 text-sm transition-colors",
                  active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
                )}
                href={item.path}
              >
                {item.name}
              </Link>
            );
          })}
        </nav>
        {permissions.length === 0 ? (
          <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
            No assigned permissions found. Contact your admin to request access.
          </p>
        ) : null}
      </>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="h-8 w-8 p-0 md:hidden"
              onClick={() => setMobileNavOpen((prev) => !prev)}
              aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
            >
              {mobileNavOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </Button>
            <p className="text-lg font-semibold">AIRIS</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs uppercase tracking-wide text-slate-600">
              {role ?? "unknown"}
            </span>
            <Button variant="outline" className="h-8 px-3" onClick={onLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>
      {mobileNavOpen ? (
        <div className="mx-auto max-w-6xl px-4 pt-3 md:hidden">
          <aside className="rounded-lg border border-slate-200 bg-white p-2">{renderNav()}</aside>
        </div>
      ) : null}
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[220px_1fr]">
        <aside className="hidden h-fit rounded-lg border border-slate-200 bg-white p-2 md:block">
          {renderNav()}
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
