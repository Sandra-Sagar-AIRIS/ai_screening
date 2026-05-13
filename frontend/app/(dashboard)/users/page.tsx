"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { listOrganizationRoles } from "@/lib/api/roles";
import { getUsers, updateUserRole } from "@/lib/api/users";
import type { OrganizationRole, OrganizationUser, UserRoleOption } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { Users, Shield, Clock, Search, MoreHorizontal, UserCog } from "lucide-react";

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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-6 h-6 text-[#FF5A1F]" />
            Organization Users
          </h1>
          <p className="text-sm text-gray-500 mt-1">Manage team members and their access levels</p>
        </div>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <p className="text-sm text-slate-500">Loading users...</p>
        </div>
      ) : null}
      
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center gap-2">
          {error}
        </div>
      ) : null}
      
      {updateError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center gap-2">
          {updateError}
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <UserCog className="w-5 h-5 text-gray-400" />
              Active Users
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50">
                <tr className="border-b border-gray-200 text-slate-500 font-medium">
                  <th className="px-6 py-4">User</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4">Joined Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-[#FF5A1F]/10 flex items-center justify-center text-[#FF5A1F] font-medium text-xs">
                          {user.email.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium text-gray-900">{user.email}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-slate-400" />
                        <select
                          className="h-8 rounded-md border border-slate-200 bg-white px-2 py-1 text-sm text-gray-700 shadow-sm focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] outline-none transition-all disabled:opacity-50"
                          value={user.role}
                          disabled={updatingUserId === user.id}
                          onChange={(event) => onRoleChange(user.id, event.target.value as UserRoleOption)}
                        >
                          {roleChoices.map((option) => (
                            <option key={option.id} value={option.key}>
                              {option.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        user.type === 'internal' 
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {user.type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 flex items-center gap-2">
                      <Clock className="w-4 h-4 text-slate-400" />
                      {new Date(user.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {users.length === 0 ? (
              <div className="py-12 text-center">
                <Users className="w-12 h-12 text-slate-200 mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-900">No users found</p>
                <p className="text-sm text-slate-500 mt-1">There are currently no users in this organization.</p>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>

  );
}
