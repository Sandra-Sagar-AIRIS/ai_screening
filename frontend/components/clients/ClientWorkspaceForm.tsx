"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Client, ClientCreatePayload, ClientUpdatePayload } from "@/lib/api/types";

type Props = {
  initial?: Client;
  onSubmit: (payload: ClientCreatePayload | ClientUpdatePayload) => Promise<void>;
  onCancel: () => void;
  isEdit?: boolean;
};

const INDUSTRIES = [
  "Technology",
  "Finance",
  "Healthcare",
  "Retail",
  "Manufacturing",
  "Education",
  "Media",
  "Consulting",
  "Legal",
  "Real Estate",
  "Other",
];

export function ClientWorkspaceForm({ initial, onSubmit, onCancel, isEdit = false }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [industry, setIndustry] = useState(initial?.industry ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [website, setWebsite] = useState(initial?.website ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [location, setLocation] = useState(initial?.location ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Client name is required."); return; }
    if (!isEdit && !industry.trim()) { setError("Industry is required."); return; }
    if (!isEdit && !email.trim()) { setError("Contact email is required."); return; }

    setLoading(true);
    try {
      const payload: ClientCreatePayload = {
        name: name.trim(),
        industry: industry.trim(),
        email: email.trim(),
        website: website.trim() || undefined,
        phone: phone.trim() || undefined,
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
      };
      await onSubmit(payload);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409") || msg.toLowerCase().includes("conflict")) {
        setError("A client with this name already exists in your organization.");
      } else {
        setError(msg || "An error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-1">
        <Label htmlFor="client-name">
          Client Name <span className="text-red-500">*</span>
        </Label>
        <Input
          id="client-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Acme Corporation"
          required
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="client-industry">
          Industry {!isEdit && <span className="text-red-500">*</span>}
        </Label>
        <select
          id="client-industry"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="">Select industry…</option>
          {INDUSTRIES.map((ind) => (
            <option key={ind} value={ind}>{ind}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="client-email">
          Contact Email {!isEdit && <span className="text-red-500">*</span>}
        </Label>
        <Input
          id="client-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="contact@client.com"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="client-website">Website</Label>
          <Input
            id="client-website"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://client.com"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="client-phone">Phone</Label>
          <Input
            id="client-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 555 000 0000"
          />
        </div>
      </div>

      <div className="space-y-1">
        <Label htmlFor="client-location">Location</Label>
        <Input
          id="client-location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="City, Country"
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="client-notes">Notes</Label>
        <textarea
          id="client-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
          placeholder="Internal notes about this client…"
        />
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={loading}
          className="bg-[#FF5A1F] hover:bg-[#e04e1a] text-white"
        >
          {loading ? "Saving…" : isEdit ? "Save Changes" : "Create Client"}
        </Button>
      </div>
    </form>
  );
}
