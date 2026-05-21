"use client";

/** AIR-509: Notes timeline with author and timestamp; AIR-508 admin soft-hide. */

import { useCallback, useEffect, useState } from "react";
import { EyeOff } from "lucide-react";
import { ApiError, invalidateApiCache } from "@/lib/api/client";
import {
  createCandidateNote,
  getCandidateNotes,
  hideCandidateNote,
  type CandidateNote,
} from "@/lib/api/candidateNotes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function formatAuthor(note: CandidateNote): string {
  if (note.author_email) return note.author_email;
  if (note.author_role) return note.author_role;
  if (note.author_user_id) return "Team member";
  return "Unknown";
}

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

type CandidateNotesPanelProps = {
  candidateId: string;
  isAdmin?: boolean;
  /** Compact layout for list-page modal */
  compact?: boolean;
  /** Refetch candidate interactions for Communication Hub timeline */
  onTimelineActivity?: () => void | Promise<void>;
};

export function CandidateNotesPanel({
  candidateId,
  isAdmin = false,
  compact = false,
  onTimelineActivity,
}: CandidateNotesPanelProps) {
  const [notes, setNotes] = useState<CandidateNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [hidingId, setHidingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getCandidateNotes(candidateId, 100, 0);
      setNotes(res.data ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotes([]);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load notes.");
        setNotes([]);
      }
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    void loadNotes();
  }, [loadNotes]);

  async function handleSave() {
    const text = input.trim();
    if (!text) return;
    setSaving(true);
    setError(null);
    try {
      await createCandidateNote(candidateId, text);
      invalidateApiCache(`/candidates/${candidateId}/notes`);
      setInput("");
      await loadNotes();
      await onTimelineActivity?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add note.");
    } finally {
      setSaving(false);
    }
  }

  async function handleHide(noteId: string) {
    if (!isAdmin) return;
    setHidingId(noteId);
    setError(null);
    try {
      await hideCandidateNote(candidateId, noteId);
      invalidateApiCache(`/candidates/${candidateId}/notes`);
      await loadNotes();
      await onTimelineActivity?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to hide note.");
    } finally {
      setHidingId(null);
    }
  }

  return (
    <div className={compact ? "space-y-3" : "space-y-4"}>
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add note..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSave();
            }
          }}
        />
        <Button onClick={() => void handleSave()} disabled={saving || !input.trim()}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
      {error ? <p className="text-xs text-red-600">{error}</p> : null}
      <div
        className={
          compact
            ? "max-h-64 space-y-0 overflow-auto rounded border border-slate-200"
            : "overflow-hidden rounded-lg border border-slate-200"
        }
      >
        {loading ? (
          <p className="p-3 text-xs text-slate-500">Loading notes...</p>
        ) : notes.length === 0 ? (
          <p className="p-3 text-xs text-slate-500">No notes yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {notes.map((note) => (
              <li key={note.id} className="relative px-3 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-800 whitespace-pre-wrap">{note.content}</p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      <span className="font-medium text-slate-600">{formatAuthor(note)}</span>
                      <span className="mx-1">·</span>
                      {formatWhen(note.created_at)}
                      {isAdmin && note.hidden ? (
                        <span className="ml-1 italic text-amber-600">(hidden from team)</span>
                      ) : null}
                    </p>
                  </div>
                  {isAdmin && !note.hidden ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="shrink-0 h-8 px-2 text-slate-500 hover:text-slate-700"
                      title="Hide note from team (soft-hide)"
                      disabled={hidingId === note.id}
                      onClick={() => void handleHide(note.id)}
                    >
                      <EyeOff className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
