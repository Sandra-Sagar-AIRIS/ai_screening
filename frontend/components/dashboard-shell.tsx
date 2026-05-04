"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/candidates", label: "Candidates" },
  { href: "/jobs", label: "Jobs" },
  { href: "/vendor/jobs", label: "My Jobs" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/invite", label: "Invite" },
  { href: "/invites", label: "Invites" },
  { href: "/users", label: "Users" },
  { href: "/roles", label: "Roles" },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const permissions = useAuthStore((state) => state.permissions);
  const hydrate = useAuthStore((state) => state.hydrate);
  const refreshPermissions = useAuthStore((state) => state.refreshPermissions);
  const clearToken = useAuthStore((state) => state.clearToken);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!token || permissions.length > 0) {
      return;
    }
    void refreshPermissions();
  }, [token, permissions.length, refreshPermissions]);

  useEffect(() => {
    if (token === null) {
      router.replace("/login");
    }
  }, [router, token]);

  useEffect(() => {
    if (token && role === null) {
      router.replace("/login");
    }
  }, [role, router, token]);

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
      return permissions.includes("jobs:read_limited");
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

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <p className="text-lg font-semibold">AIRIS</p>
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs uppercase tracking-wide text-slate-600">
              {role ?? "unknown"}
            </span>
            <Button variant="outline" onClick={onLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-[220px_1fr]">
        <aside className="rounded-lg border border-slate-200 bg-white p-2">
          <nav className="space-y-1">
            {navItems.map((item) => (
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
        <main>
          {canAccessPage() ? (
            children
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Access restricted</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-slate-600">
                You do not have permission to view this page.
              </CardContent>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}
