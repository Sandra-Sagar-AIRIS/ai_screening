"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { Role } from "@/lib/api";
import { Plus, Shield, Settings2, ShieldCheck } from "lucide-react";

type RoleTableProps = {
  roles: Role[];
  loading?: boolean;
  error?: string | null;
};

export function RoleTable({ roles, loading = false, error = null }: RoleTableProps) {
  const empty = !loading && !error && roles.length === 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="p-5 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <Shield className="w-5 h-5 text-gray-400" />
          Configured Roles
        </h2>
        <Link href="/roles/create">
          <Button className="bg-[#FF5A1F] hover:bg-[#E04D1A] text-white flex items-center gap-2">
            <Plus className="w-4 h-4" /> New Role
          </Button>
        </Link>
      </div>
      
      <div className="p-0">
        {error ? (
          <div className="m-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center gap-2">
            {error}
          </div>
        ) : null}

        {!loading && !error && empty ? (
          <div className="py-12 text-center">
            <ShieldCheck className="w-12 h-12 text-slate-200 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-900">No roles found</p>
            <p className="text-sm text-slate-500 mt-1">Create a role to assign permissions for your organization.</p>
            <div className="mt-6 flex justify-center">
              <Link href="/roles/create">
                <Button className="bg-[#FF5A1F] hover:bg-[#E04D1A] text-white">Create your first role</Button>
              </Link>
            </div>
          </div>
        ) : null}

        {!loading && !error && !empty ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50">
                <tr className="border-b border-gray-200 text-slate-500 font-medium">
                  <th className="px-6 py-4">Role Name</th>
                  <th className="px-6 py-4 text-slate-400 font-normal">Permissions</th>
                  <th className="px-6 py-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {roles.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 font-medium text-gray-900">
                        {r.name === 'admin' || r.name === 'recruiter' ? (
                          <ShieldCheck className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <Settings2 className="w-4 h-4 text-slate-400" />
                        )}
                        {r.name}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-400" title="Set permissions when editing the role">
                      —
                    </td>
                    <td className="px-6 py-4">
                      <Link href={`/roles/${r.id}`} className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors">
                        Edit
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}
