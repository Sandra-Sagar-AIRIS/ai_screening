"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getRolePermissions, updateRolePermissions } from "@/lib/api/roles";
import type { RoleKey, RolePermissionsResponse } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

const roleOrder: RoleKey[] = ["admin", "recruiter", "client_viewer"];
const CRITICAL_ADMIN_PERMISSION = "organization:manage";

const PERMISSION_CONFIG = {
  candidates: {
    label: "Candidates",
    actions: {
      create: "Can create candidate records",
      read: "Can view candidate profiles",
      update: "Can edit candidate details",
      delete: "Can delete candidate records",
    },
  },
  clients: {
    label: "Clients",
    actions: {
      create: "Can create client organizations",
      read: "Can view client records",
      update: "Can update client details",
    },
  },
  interviews: {
    label: "Interviews",
    actions: {
      create: "Can schedule interviews",
      read: "Can view interview details",
      update: "Can edit interview details",
    },
  },
  jobs: {
    label: "Jobs",
    actions: {
      create: "Can create job postings",
      read: "Can view jobs",
      update: "Can edit jobs",
      delete: "Can delete jobs",
    },
  },
  organization: {
    label: "Organization",
    actions: {
      manage: "Can manage organization-level settings",
    },
  },
  pipeline: {
    label: "Pipeline",
    actions: {
      create: "Can add candidates to pipeline",
      read: "Can view pipeline stages",
      update: "Can move candidates across stages",
    },
  },
  users: {
    label: "Users",
    actions: {
      invite: "Can invite and manage organization users",
    },
  },
} as const;

const roleDescriptions: Record<RoleKey, string> = {
  admin: "Full access including organization settings and role configuration.",
  recruiter: "Can manage candidates, jobs, interviews, and pipeline operations.",
  client_viewer: "Can review shared client-facing records with limited edit access.",
};

type PermissionConfig = typeof PERMISSION_CONFIG;
type ModuleKey = keyof PermissionConfig;

type PermissionItem = {
  value: string;
  actionLabel: string;
  description: string;
};

type PermissionGroup = {
  moduleKey: string;
  moduleLabel: string;
  permissions: PermissionItem[];
};

function formatLabel(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function buildPermissionGroups(): PermissionGroup[] {
  return (Object.keys(PERMISSION_CONFIG) as ModuleKey[]).map((moduleKey) => {
    const mod = PERMISSION_CONFIG[moduleKey];
    const permissions = Object.entries(mod.actions).map(([actionKey, description]) => ({
      value: `${moduleKey}:${actionKey}`,
      actionLabel: formatLabel(actionKey),
      description,
    }));
    return {
      moduleKey,
      moduleLabel: mod.label,
      permissions,
    };
  });
}

function sortPermissions(values: string[]) {
  return [...values].sort();
}

function isRoleDirty(current: string[], initial: string[]) {
  const currentSorted = sortPermissions(current);
  const initialSorted = sortPermissions(initial);
  if (currentSorted.length !== initialSorted.length) {
    return true;
  }
  return currentSorted.some((value, index) => value !== initialSorted[index]);
}

function normalizeRoleData(response: RolePermissionsResponse): RolePermissionsResponse {
  return {
    admin: sortPermissions(response.admin ?? []),
    recruiter: sortPermissions(response.recruiter ?? []),
    client_viewer: sortPermissions(response.client_viewer ?? []),
  };
}

export default function RolesPage() {
  const role = useAuthStore((state) => state.role);
  const [data, setData] = useState<RolePermissionsResponse | null>(null);
  const [initialData, setInitialData] = useState<RolePermissionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRole, setSavingRole] = useState<RoleKey | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedModules, setExpandedModules] = useState<Record<RoleKey, Record<string, boolean>>>({
    admin: {},
    recruiter: {},
    client_viewer: {},
  });
  const permissionGroups = buildPermissionGroups();

  const isAdmin = role === "admin";

  useEffect(() => {
    async function loadData() {
      if (!isAdmin) {
        setLoading(false);
        return;
      }

      try {
        const response = normalizeRoleData(await getRolePermissions());
        setData(response);
        setInitialData(response);
        const defaultExpanded: Record<RoleKey, Record<string, boolean>> = {
          admin: {},
          recruiter: {},
          client_viewer: {},
        };
        for (const roleKey of roleOrder) {
          for (const group of permissionGroups) {
            defaultExpanded[roleKey][group.moduleKey] = true;
          }
        }
        setExpandedModules(defaultExpanded);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load role permissions");
        }
      } finally {
        setLoading(false);
      }
    }

    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  function togglePermission(roleKey: RoleKey, permission: string, checked: boolean) {
    if (!data) {
      return;
    }
    if (roleKey === "admin" && permission === CRITICAL_ADMIN_PERMISSION) {
      return;
    }
    const existing = new Set(data[roleKey]);
    if (checked) {
      existing.add(permission);
    } else {
      existing.delete(permission);
    }
    if (roleKey === "admin") {
      existing.add(CRITICAL_ADMIN_PERMISSION);
    }
    setData({
      ...data,
      [roleKey]: Array.from(existing).sort(),
    });
  }

  function toggleModule(roleKey: RoleKey, modulePermissions: string[], checked: boolean) {
    if (!data) {
      return;
    }
    const existing = new Set(data[roleKey]);
    for (const permission of modulePermissions) {
      if (roleKey === "admin" && permission === CRITICAL_ADMIN_PERMISSION) {
        continue;
      }
      if (checked) {
        existing.add(permission);
      } else {
        existing.delete(permission);
      }
    }
    if (roleKey === "admin") {
      existing.add(CRITICAL_ADMIN_PERMISSION);
    }
    setData({
      ...data,
      [roleKey]: Array.from(existing).sort(),
    });
  }

  function toggleModuleExpanded(roleKey: RoleKey, moduleKey: string) {
    setExpandedModules((prev) => ({
      ...prev,
      [roleKey]: {
        ...prev[roleKey],
        [moduleKey]: !prev[roleKey]?.[moduleKey],
      },
    }));
  }

  function resetRoleToDefault(roleKey: RoleKey) {
    if (!data || !initialData) {
      return;
    }
    const nextPermissions = [...initialData[roleKey]];
    if (roleKey === "admin" && !nextPermissions.includes(CRITICAL_ADMIN_PERMISSION)) {
      nextPermissions.push(CRITICAL_ADMIN_PERMISSION);
    }
    setData({
      ...data,
      [roleKey]: sortPermissions(nextPermissions),
    });
    setSuccessMessage(`Reset ${roleKey} to default permissions.`);
  }

  async function saveRole(roleKey: RoleKey) {
    if (!data || !initialData) {
      return;
    }
    setSuccessMessage(null);
    setError(null);
    setSavingRole(roleKey);
    try {
      const payloadPermissions =
        roleKey === "admin"
          ? Array.from(new Set([...data[roleKey], CRITICAL_ADMIN_PERMISSION])).sort()
          : data[roleKey];
      await updateRolePermissions(roleKey, { permissions: payloadPermissions });
      console.info("[audit] role_permissions_updated", {
        role: roleKey,
        permissionsCount: payloadPermissions.length,
        updatedAt: new Date().toISOString(),
      });
      const nextData = { ...data, [roleKey]: payloadPermissions };
      const nextInitialData = { ...initialData, [roleKey]: payloadPermissions };
      setData(nextData);
      setInitialData(nextInitialData);
      setSuccessMessage(`Saved permissions for ${roleKey}.`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to save role permissions");
      }
    } finally {
      setSavingRole(null);
    }
  }

  if (!isAdmin) {
    return <p className="text-sm text-slate-600">Only admins can manage role permissions.</p>;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Role permissions</h1>
      {loading ? <p className="text-sm text-slate-600">Loading role permissions...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {successMessage ? <p className="text-sm text-emerald-700">{successMessage}</p> : null}

      {!loading && data
        ? roleOrder.map((roleKey) => (
            <Card key={roleKey}>
              <CardHeader className="space-y-3">
                <div className="sticky top-0 z-10 -mx-6 border-b border-slate-200 bg-white px-6 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle className="capitalize">{roleKey.replace("_", " ")}</CardTitle>
                      <p className="mt-1 text-sm text-slate-600">{roleDescriptions[roleKey]}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        disabled={!initialData || !isRoleDirty(data[roleKey], initialData[roleKey])}
                        onClick={() => resetRoleToDefault(roleKey)}
                      >
                        Reset to default
                      </Button>
                      <Button
                        disabled={
                          savingRole === roleKey || !initialData || !isRoleDirty(data[roleKey], initialData[roleKey])
                        }
                        onClick={() => saveRole(roleKey)}
                      >
                        {savingRole === roleKey ? "Saving..." : "Save"}
                      </Button>
                    </div>
                  </div>
                </div>
                <div>
                  <div>
                    {initialData && isRoleDirty(data[roleKey], initialData[roleKey]) ? (
                      <p className="text-sm font-medium text-amber-700">Unsaved changes</p>
                    ) : (
                      <p className="text-sm text-slate-500">No pending changes</p>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {permissionGroups.map((group) => {
                  const modulePermissions = group.permissions.map((item) => item.value);
                  const selectedCount = modulePermissions.filter((permission) => data[roleKey].includes(permission)).length;
                  const allSelected = selectedCount === modulePermissions.length;
                  const partiallySelected = selectedCount > 0 && !allSelected;
                  const isExpanded = expandedModules[roleKey]?.[group.moduleKey] ?? true;
                  return (
                    <div key={`${roleKey}-${group.moduleKey}`} className="space-y-2 rounded-md border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <label className="flex items-center gap-2 text-sm font-medium text-slate-900">
                          <input
                            type="checkbox"
                            checked={allSelected}
                            onChange={(event) => toggleModule(roleKey, modulePermissions, event.target.checked)}
                          />
                          <span>{group.moduleLabel} (select all)</span>
                          {partiallySelected ? <span className="text-xs font-normal text-slate-500">Partially selected</span> : null}
                        </label>
                        <Button variant="ghost" onClick={() => toggleModuleExpanded(roleKey, group.moduleKey)}>
                          {isExpanded ? "Collapse" : "Expand"}
                        </Button>
                      </div>
                      {isExpanded ? (
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          {group.permissions.map((item) => {
                            const isLocked = roleKey === "admin" && item.value === CRITICAL_ADMIN_PERMISSION;
                            return (
                              <label key={`${roleKey}-${item.value}`} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                                <span className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={data[roleKey].includes(item.value)}
                                    disabled={isLocked}
                                    onChange={(event) => togglePermission(roleKey, item.value, event.target.checked)}
                                  />
                                  <span className="font-medium">{item.actionLabel}</span>
                                  {isLocked ? <span className="text-xs text-slate-500">(required)</span> : null}
                                </span>
                                <span className="mt-1 block pl-6 text-xs text-slate-500">{item.description}</span>
                              </label>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ))
        : null}
    </section>
  );
}
