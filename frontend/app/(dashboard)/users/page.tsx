"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { listOrganizationRoles } from "@/lib/api/roles";
import { getUsers, updateUserRole } from "@/lib/api/users";
import type { OrganizationRole, OrganizationUser, UserRoleOption } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

export default function UsersPage() {
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [roleChoices, setRoleChoices] = useState<OrganizationRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);
  const role = useAuthStore((state) => state.role);

  const canManageUsers = role === "admin" || permissions.includes("users:invite");

  useEffect(() => {
    async function loadData() {
      if (!canManageUsers) {
        setLoading(false);
        return;
      }

      try {
        const [data, roles] = await Promise.all([getUsers(), listOrganizationRoles()]);
        setUsers(data);
        setRoleChoices(roles);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load users");
        }
      } finally {
        setLoading(false);
      }
    }

    void loadData();
  }, [canManageUsers]);

  async function onRoleChange(userId: string, newRole: UserRoleOption) {
    setUpdateError(null);
    setUpdatingUserId(userId);
    try {
      const updated = await updateUserRole(userId, { role: newRole });
      setUsers((prev) => prev.map((user) => (user.id === updated.id ? updated : user)));
    } catch (err) {
      if (err instanceof ApiError) {
        setUpdateError(err.message);
      } else {
        setUpdateError("Unable to update user role");
      }
    } finally {
      setUpdatingUserId(null);
    }
  }

  if (!canManageUsers) {
    return <p className="text-sm text-slate-600">You do not have permission to manage users.</p>;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Users</h1>
      {loading ? <p className="text-sm text-slate-600">Loading users...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {updateError ? <p className="text-sm text-red-600">{updateError}</p> : null}

      {!loading && !error ? (
        <Card>
          <CardHeader>
            <CardTitle>User List</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="px-2 py-2">Email</th>
                    <th className="px-2 py-2">Role</th>
                    <th className="px-2 py-2">Type</th>
                    <th className="px-2 py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} className="border-b border-slate-100">
                      <td className="px-2 py-2">{user.email}</td>
                      <td className="px-2 py-2">
                        <select
                          className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
                          value={user.role}
                          disabled={updatingUserId === user.id}
                          onChange={(event) => onRoleChange(user.id, event.target.value as UserRoleOption)}
                        >
                          {roleChoices.map((option) => (
                            <option key={option.id} value={option.key}>
                              {option.name} ({option.key})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-2 py-2">{user.type}</td>
                      <td className="px-2 py-2">{new Date(user.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {users.length === 0 ? <p className="mt-3 text-sm text-slate-500">No users found.</p> : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
