"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { assignRecruiters, listClientRecruiters, removeRecruiterFromClient } from "@/lib/api/clients";
import type { ClientRecruiter } from "@/lib/api/types";

type UserOption = {
  id: string;
  name: string;
  email: string;
};

type Props = {
  clientId: string;
  availableRecruiters: UserOption[];
};

export function RecruiterAssignmentSelector({ clientId, availableRecruiters }: Props) {
  const [assignments, setAssignments] = useState<ClientRecruiter[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listClientRecruiters(clientId).then(setAssignments).catch(() => {});
  }, [clientId]);

  const assignedIds = new Set(assignments.map((a) => a.recruiter_id));
  const unassigned = availableRecruiters.filter((r) => !assignedIds.has(r.id));

  async function handleAssign() {
    if (!selectedId) return;
    setError(null);
    setLoading(true);
    try {
      const updated = await assignRecruiters(clientId, [selectedId]);
      setAssignments(updated);
      setSelectedId("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to assign recruiter.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(recruiterId: string) {
    setError(null);
    try {
      await removeRecruiterFromClient(clientId, recruiterId);
      setAssignments((prev) => prev.filter((a) => a.recruiter_id !== recruiterId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove recruiter.");
    }
  }

  function recruiterName(recruiterId: string) {
    return availableRecruiters.find((r) => r.id === recruiterId)?.name ?? recruiterId.slice(0, 8) + "…";
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Assigned list */}
      {assignments.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {assignments.map((a) => (
            <span
              key={a.recruiter_id}
              className="flex items-center gap-1 rounded-full bg-orange-50 border border-[#FF5A1F]/20 px-2.5 py-0.5 text-xs font-medium text-[#FF5A1F]"
            >
              {recruiterName(a.recruiter_id)}
              <button
                type="button"
                onClick={() => handleRemove(a.recruiter_id)}
                className="ml-1 text-[#FF5A1F]/60 hover:text-red-500"
                aria-label="Remove recruiter"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 italic">No recruiters assigned yet.</p>
      )}

      {/* Add recruiter */}
      {unassigned.length > 0 && (
        <div className="flex gap-2">
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="flex h-8 flex-1 rounded-md border border-input bg-background px-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">Add recruiter…</option>
            {unassigned.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.email})
              </option>
            ))}
          </select>
          <Button
            type="button"
            size="sm"
            onClick={handleAssign}
            disabled={!selectedId || loading}
            className="bg-[#FF5A1F] hover:bg-[#e04e1a] text-white"
          >
            Assign
          </Button>
        </div>
      )}
    </div>
  );
}
