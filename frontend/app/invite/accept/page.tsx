"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordField } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { acceptInvite } from "@/lib/api/invites";

function AcceptInviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!token) {
      setError("Invite token is missing from the URL.");
      return;
    }

    if (!password) {
      setError("Please enter a password.");
      return;
    }

    setLoading(true);
    try {
      await acceptInvite({ token, password });
      router.push("/login?inviteAccepted=1");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to accept invite. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Accept your invite" subtitle="Set a password to activate your account.">
      <form className="space-y-4" onSubmit={onSubmit}>
        <PasswordField id="password" label="Password" value={password} onChange={setPassword} />
        {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        {!token ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
            Missing token. Open this page using the invite link.
          </p>
        ) : null}
        <Button className="w-full" type="submit" disabled={loading || !token}>
          {loading ? "Accepting invite..." : "Accept invite"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={<p>Loading...</p>}>
      <AcceptInviteForm />
    </Suspense>
  );
}
