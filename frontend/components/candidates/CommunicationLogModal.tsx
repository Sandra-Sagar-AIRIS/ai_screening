"use client";

/** AIR-567: Manual call / meeting log via existing interactions API. */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";

type LogKind = "call" | "meeting";

type CommunicationLogModalProps = {
  kind: LogKind;
  open: boolean;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (payload: { title: string; body: string; durationMinutes?: number }) => Promise<void>;
};

export function CommunicationLogModal({
  kind,
  open,
  saving,
  error,
  onClose,
  onSave,
}: CommunicationLogModalProps) {
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [duration, setDuration] = useState("");

  if (!open) return null;

  const label = kind === "call" ? "Log phone call" : "Log in-person meeting";

  async function handleSubmit() {
    const trimmedTitle = title.trim() || (kind === "call" ? "Phone call" : "In-person meeting");
    const trimmedNotes = notes.trim();
    const durationMinutes = duration.trim() ? Number(duration) : undefined;
    await onSave({
      title: trimmedTitle,
      body: trimmedNotes || trimmedTitle,
      durationMinutes: Number.isFinite(durationMinutes) ? durationMinutes : undefined,
    });
    setTitle("");
    setNotes("");
    setDuration("");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-labelledby="comm-log-title"
        className="w-full max-w-md rounded-xl border border-gray-200 bg-white shadow-lg"
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
          <h3 id="comm-log-title" className="text-sm font-semibold text-gray-900">
            {label}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3 p-4">
          {error ? <p className="text-xs text-red-600">{error}</p> : null}
          <div>
            <label className="text-xs font-medium text-gray-600">Title</label>
            <Input
              className="mt-1"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={kind === "call" ? "Phone call with candidate" : "Meeting with candidate"}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600">Notes</label>
            <textarea
              className="mt-1 w-full min-h-[88px] rounded-md border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#FF5A1F]"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Summary of the conversation..."
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600">Duration (minutes, optional)</label>
            <Input
              className="mt-1"
              type="number"
              min={0}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="30"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-gray-100 px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            size="sm"
            className="bg-[#FF5A1F] hover:bg-[#E54E1A] text-white"
            onClick={() => void handleSubmit()}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save log"}
          </Button>
        </div>
      </div>
    </div>
  );
}
