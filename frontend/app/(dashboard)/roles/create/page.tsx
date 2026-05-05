"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PermissionGroup } from "@/components/PermissionGroup";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { assignPermissions, createRole, getPermissions, type PermissionModuleGroup } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

const ROLE_FLASH_KEY = "airis_role_flash";

function PageLoader() {
  return (
    <div className="flex min-h-[200px] items-center justify-center">
      <p className="text-sm text-slate-600">Loading...</p>
    </div>
  );
}

function mapCreateError(err: unknown): string {
  if (err instanceof ApiError) {
    const text = (err.message || "").toLowerCase();
    if (err.status === 409 || text.includes("unique") || text.includes("duplicate") || text.includes("already exists")) {
      return "A role with this name already exists. Choose a different name.";
    }
    return "Something went wrong. Please try again.";
  }
  return "Unable to create role. Please try again.";
}

export default function CreateRolePage() {
  const router = useRouter();
  const role = useAuthStore((state) => state.role);
  const [name, setName] = useState("");
  const [groups, setGroups] = useState<PermissionModuleGroup[]>([]);
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPermissions() {
      if (role !== "admin") {
        setLoading(false);
        return;
      }
      setError(null);
      try {
        const data = await getPermissions();
        setGroups(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError("Failed to load permissions. Please refresh the page.");
        } else {
          setError("Something went wrong loading permissions.");
        }
      } finally {
        setLoading(false);
      }
    }
    void loadPermissions();
  }, [role]);

  function onTogglePermission(code: string, checked: boolean) {
    setSelectedPermissions((prev) => {
      if (checked) {
        return prev.includes(code) ? prev : [...prev, code];
      }
      return prev.filter((value) => value !== code);
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) {
      return;
    }

    setError(null);

    const roleName = name.trim();
    if (!roleName) {
      setError("Enter a role name.");
      return;
    }

    setSaving(true);
    try {
      const created = await createRole({ name: roleName });
      await assignPermissions(created.id, selectedPermissions);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(ROLE_FLASH_KEY, "created");
      }
      router.push("/roles");
      router.refresh();
    } catch (err) {
      setError(mapCreateError(err));
    } finally {
      setSaving(false);
    }
  }

  if (role !== "admin") {
    return <p className="text-sm text-slate-600">Only admins can create roles.</p>;
  }

  if (loading) {
    return <PageLoader />;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Create Role</h1>
      <Card>
        <CardHeader>
          <CardTitle>Role details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900" htmlFor="role-name">
                Role Name
              </label>
              <Input
                id="role-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Senior Recruiter"
                disabled={saving}
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-900">Permissions</p>
              {groups.length === 0 && !error ? (
                <p className="text-sm text-slate-500">No permissions available.</p>
              ) : null}
              {groups.length > 0 ? (
                <PermissionGroup
                  groups={groups}
                  selectedPermissions={selectedPermissions}
                  onTogglePermission={onTogglePermission}
                  disabled={saving}
                />
              ) : null}
            </div>

            {error ? (
              <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
                {error}
              </p>
            ) : null}

            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => router.push("/roles")} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Role"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
