"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { createInvite } from "@/lib/api/invites";
import { listOrganizationRoles } from "@/lib/api/roles";

export default function InvitePage() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("");
  const [roleChoices, setRoleChoices] = useState<{ key: string; name: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(true);

  useEffect(() => {
    async function loadRoles() {
      try {
        const roles = await listOrganizationRoles();
        const choices = roles
          .filter((r) => r.key !== "admin")
          .map((r) => ({ key: r.key, name: r.name }));
        setRoleChoices(choices);
        setRole((prev) => {
          if (prev) {
            return prev;
          }
          const recruiter = choices.find((c) => c.key === "recruiter");
          return recruiter?.key ?? choices[0]?.key ?? "";
        });
      } catch {
        setError("Unable to load roles for invite.");
      } finally {
        setLoadingRoles(false);
      }
    }
    void loadRoles();
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError("Please enter an email address.");
      return;
    }
    if (!role) {
      setError("Select a role.");
      return;
    }

    setLoading(true);
    try {
      await createInvite({
        email: normalizedEmail,
        role,
      });
      setSuccess("Invite sent successfully");
      setEmail("");
      const recruiter = roleChoices.find((c) => c.key === "recruiter");
      setRole(recruiter?.key ?? roleChoices[0]?.key ?? "");
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
                disabled={loadingRoles || roleChoices.length === 0}
                onChange={(event) => setRole(event.target.value)}
              >
                {roleChoices.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.name} ({option.key})
                  </option>
                ))}
              </select>
            </div>

            {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            {success ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}

            <Button type="submit" disabled={loading || loadingRoles || !role}>
              {loading ? "Creating invite..." : "Create invite"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
