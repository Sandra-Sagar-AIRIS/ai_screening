"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CandidateCreatePayload } from "@/lib/api/types";

type CandidateFormProps = {
  onSubmit: (payload: CandidateCreatePayload) => Promise<void>;
  isSubmitting?: boolean;
};

export function CandidateForm({ onSubmit, isSubmitting = false }: CandidateFormProps) {
  const [form, setForm] = useState<CandidateCreatePayload>({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    location: "",
    experience_summary: "",
    education: "",
    notes: "",
  });

  function updateField<K extends keyof CandidateCreatePayload>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({
      ...form,
      phone: form.phone?.trim() || undefined,
      location: form.location?.trim() || undefined,
      experience_summary: form.experience_summary?.trim() || undefined,
      education: form.education?.trim() || undefined,
      notes: form.notes?.trim() || undefined,
    });
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">First Name</label>
          <Input required value={form.first_name} onChange={(e) => updateField("first_name", e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Last Name</label>
          <Input required value={form.last_name} onChange={(e) => updateField("last_name", e.target.value)} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <Input required type="email" value={form.email} onChange={(e) => updateField("email", e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Phone (optional)</label>
          <Input value={form.phone} onChange={(e) => updateField("phone", e.target.value)} />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Location (optional)</label>
        <Input value={form.location} onChange={(e) => updateField("location", e.target.value)} />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Experience Summary</label>
        <textarea
          className="min-h-20 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          value={form.experience_summary}
          onChange={(e) => updateField("experience_summary", e.target.value)}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Education</label>
        <textarea
          className="min-h-20 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          value={form.education}
          onChange={(e) => updateField("education", e.target.value)}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">Notes</label>
        <textarea
          className="min-h-20 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          value={form.notes}
          onChange={(e) => updateField("notes", e.target.value)}
        />
      </div>

      <Button disabled={isSubmitting} type="submit">
        {isSubmitting ? "Submitting..." : "Submit Candidate"}
      </Button>
    </form>
  );
}

