"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { createInvite } from "@/lib/api/invites";
import type { InviteRole } from "@/lib/api/types";

const roleOptions: Array<{ value: InviteRole; label: string }> = [
  { value: "recruiter", label: "Recruiter" },
  { value: "client_viewer", label: "Client" },
];

export default function InvitePage() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<InviteRole>("recruiter");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setToken(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError("Please enter an email address.");
      return;
    }

    setLoading(true);
    try {
      const data = await createInvite({
        email: normalizedEmail,
        role,
      });
      setSuccess(data.message ?? "Invite created successfully.");
      setToken(data.token);
      setEmail("");
      setRole("recruiter");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to create invite. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Invite user</h1>
      <Card>
        <CardHeader>
          <CardTitle>Create invite</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="invite-email">
                Email
              </label>
              <Input
                id="invite-email"
                type="email"
                placeholder="user@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="invite-role">
                Role
              </label>
              <select
                id="invite-role"
                className="flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={role}
                onChange={(event) => setRole(event.target.value as InviteRole)}
              >
                {roleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            {success ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}
            {token ? (
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-600">Invite token</p>
                <p className="mt-1 break-all text-sm text-slate-900">{token}</p>
              </div>
            ) : null}

            <Button type="submit" disabled={loading}>
              {loading ? "Creating invite..." : "Create invite"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
