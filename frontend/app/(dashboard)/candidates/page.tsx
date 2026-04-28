"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import type { Candidate } from "@/lib/api/types";
import { CANDIDATES_CREATE_PERMISSION, hasPermission } from "@/lib/rbac";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getCandidates(50, 0);
        setCandidates(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load candidates");
        }
      }
    }
    loadData();
  }, []);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Candidates</h1>
        {hasPermission(permissions, CANDIDATES_CREATE_PERMISSION) ? <Button>Create candidate</Button> : null}
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <Card>
        <CardHeader>
          <CardTitle>Candidate List</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-600">
                  <th className="px-2 py-2">Name</th>
                  <th className="px-2 py-2">Email</th>
                  <th className="px-2 py-2">Location</th>
                  <th className="px-2 py-2">Details</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.id} className="border-b border-slate-100">
                    <td className="px-2 py-2">{candidate.first_name} {candidate.last_name}</td>
                    <td className="px-2 py-2">{candidate.email}</td>
                    <td className="px-2 py-2">{candidate.location ?? "-"}</td>
                    <td className="px-2 py-2">
                      <Link className="text-blue-600 hover:underline" href={`/candidates/${candidate.id}`}>
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
