"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "@/lib/api/auth";
import { formatApiErrorForUser } from "@/lib/api/client";
import { useAuthStore } from "@/store/auth-store";
import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordField } from "@/components/auth/password-field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inviteAccepted = searchParams.get("inviteAccepted") === "1";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError("Please enter your email address.");
      return;
    }

    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);
    try {
      const data = await login({ email: normalizedEmail, password });
      setAuth(data.access_token, data.role, data.user_type, data.organization_id, data.permissions);
      router.push("/dashboard");
    } catch (err) {
      setError(formatApiErrorForUser(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell 
      title="Sign in to your account" 
      subtitle="Enter your credentials to access your workspace."
      leftTitle="Welcome back"
      leftSubtitle="Sign in to continue to your AIRIS workspace."
    >
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label className="text-[13px] font-semibold text-gray-700" htmlFor="email">
            Work email
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>
            </div>
            <Input
              id="email"
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="pl-10 h-11 bg-white border-gray-200 text-sm focus-visible:ring-1 focus-visible:ring-[#111827] focus-visible:border-[#111827] transition-all rounded-lg"
            />
          </div>
        </div>
        <PasswordField id="password" label="Password" value={password} onChange={setPassword} />
        {inviteAccepted ? (
          <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Your account has been created. You can now log in.
          </p>
        ) : null}
        
        {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        
        <div className="pt-2 space-y-4">
          <Button 
            className="w-full h-11 bg-[#0A101D] hover:bg-gray-800 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2" 
            type="submit" 
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in"}
            {!loading && <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>}
          </Button>

          <p className="text-center text-[13px] text-gray-500 font-medium pt-2">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-[#111827] hover:underline font-semibold transition-colors">
              Create an account
            </Link>
          </p>
        </div>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p>Loading...</p>}>
      <LoginForm />
    </Suspense>
  );
}
