"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signup } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { AuthShell } from "@/components/auth/auth-shell";
import { PasswordField } from "@/components/auth/password-field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const normalizedEmail = email.trim().toLowerCase();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(normalizedEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    const trimmedOrg = organizationName.trim();
    if (!trimmedOrg) {
      setError("Please enter your organization name.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const data = await signup({
        email: normalizedEmail,
        password,
        organization_name: trimmedOrg,
      });
      setSuccess(data.message || "Account created successfully. You can now sign in.");
      setTimeout(() => {
        router.push("/login");
      }, 1000);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to create account. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell 
      title="Create your AIRIS account" 
      subtitle="Set up your account to access candidates, jobs, and pipeline."
      leftTitle="Create your workspace"
      leftSubtitle="Join AIRIS to automate workflows, engage candidates, and close more placements."
    >
      <form className="space-y-4" onSubmit={onSubmit}>
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
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="pl-10 h-11 bg-white border-gray-200 text-sm focus-visible:ring-1 focus-visible:ring-[#111827] focus-visible:border-[#111827] transition-all rounded-lg"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-[13px] font-semibold text-gray-700" htmlFor="organization">
            Organization name
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><path d="M9 22v-4h6v4"></path><path d="M8 6h.01"></path><path d="M16 6h.01"></path><path d="M12 6h.01"></path><path d="M12 10h.01"></path><path d="M12 14h.01"></path><path d="M16 10h.01"></path><path d="M16 14h.01"></path><path d="M8 10h.01"></path><path d="M8 14h.01"></path></svg>
            </div>
            <Input
              id="organization"
              type="text"
              placeholder="Your company or team name"
              value={organizationName}
              onChange={(event) => setOrganizationName(event.target.value)}
              required
              autoComplete="organization"
              className="pl-10 h-11 bg-white border-gray-200 text-sm focus-visible:ring-1 focus-visible:ring-[#111827] focus-visible:border-[#111827] transition-all rounded-lg"
            />
          </div>
        </div>

        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
          placeholder="Minimum 8 characters"
        />

        <PasswordField
          id="confirm-password"
          label="Confirm password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          placeholder="Re-enter password"
        />

        {error ? <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        {success ? <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}

        <div className="pt-1 space-y-3">
          <Button 
            className="w-full h-11 bg-[#0A101D] hover:bg-gray-800 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2" 
            type="submit" 
            disabled={loading}
          >
            {loading ? "Creating account..." : "Create account"}
            {!loading && <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>}
          </Button>

          <p className="text-center text-[13px] text-gray-500 font-medium pt-2">
            Already have an account?{" "}
            <Link href="/login" className="text-[#111827] hover:underline font-semibold transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </form>
    </AuthShell>
  );
}
