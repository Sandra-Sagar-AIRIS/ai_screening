"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Role } from "@/lib/api";

type RoleTableProps = {
  roles: Role[];
  loading?: boolean;
  error?: string | null;
};

export function RoleTable({ roles, loading = false, error = null }: RoleTableProps) {
  const empty = !loading && !error && roles.length === 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Roles</CardTitle>
        <Link href="/roles/create">
          <Button>+ New Role</Button>
        </Link>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && empty ? (
          <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center">
            <p className="text-sm text-slate-700">No roles found.</p>
            <p className="mt-2 text-sm text-slate-500">Create a role to assign permissions for your organization.</p>
            <div className="mt-4 flex justify-center">
              <Link href="/roles/create">
                <Button>Create your first role</Button>
              </Link>
            </div>
          </div>
        ) : null}

        {!loading && !error && !empty ? (
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-3 py-2 font-medium">Role Name</th>
                  <th className="px-3 py-2 font-medium text-slate-500">Permissions</th>
                  <th className="px-3 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-3 py-2">{r.name}</td>
                    <td className="px-3 py-2 text-slate-400" title="Set permissions when editing the role">
                      —
                    </td>
                    <td className="px-3 py-2">
                      <Link href={`/roles/${r.id}`} className="text-sm text-blue-600 hover:underline">
                        Edit
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
