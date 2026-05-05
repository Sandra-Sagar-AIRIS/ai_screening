"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getInvites, resendInvite } from "@/lib/api/invites";
import type { InviteListItem } from "@/lib/api/types";

function StatusBadge({ status }: { status: InviteListItem["status"] | string }) {
  const normalized = status.toLowerCase();
  const className =
    normalized === "accepted"
      ? "bg-emerald-100 text-emerald-700"
      : "bg-amber-100 text-amber-700";
  return <span className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${className}`}>{status}</span>;
}

export default function InvitesPage() {
  const [invites, setInvites] = useState<InviteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);

  useEffect(() => {
    async function loadInvites() {
      try {
        const data = await getInvites();
        setInvites(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load invites");
        }
      } finally {
        setLoading(false);
      }
    }
    void loadInvites();
  }, []);

  async function onResend(inviteId: string) {
    setError(null);
    setMessage(null);
    setResendingId(inviteId);
    try {
      const response = await resendInvite(inviteId);
      setMessage(response.message ?? "Invite resent successfully.");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to resend invite");
      }
    } finally {
      setResendingId(null);
    }
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Invites</h1>
      {loading ? <p className="text-sm text-slate-600">Loading invites...</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}

      {!loading ? (
        <Card>
          <CardHeader>
            <CardTitle>Organization invites</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="px-2 py-2">Email</th>
                    <th className="px-2 py-2">Role</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Created</th>
                    <th className="px-2 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((invite) => {
                    const isAccepted = invite.status.toLowerCase() === "accepted";
                    return (
                      <tr key={invite.id} className="border-b border-slate-100">
                        <td className="px-2 py-2">{invite.email}</td>
                        <td className="px-2 py-2">{invite.role}</td>
                        <td className="px-2 py-2">
                          <StatusBadge status={invite.status} />
                        </td>
                        <td className="px-2 py-2">{new Date(invite.created_at).toLocaleString()}</td>
                        <td className="px-2 py-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isAccepted || resendingId === invite.id}
                            onClick={() => onResend(invite.id)}
                          >
                            {resendingId === invite.id ? "Resending..." : "Resend invite"}
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {invites.length === 0 ? <p className="mt-3 text-sm text-slate-500">No invites found.</p> : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
