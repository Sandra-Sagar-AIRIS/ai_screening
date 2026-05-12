"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Save, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { upsertNote } from "@/lib/api/interviews";
import type { InterviewNote } from "@/lib/api/types";

const SECTIONS = [
  { key: null, label: "General Notes" },
  { key: "technical", label: "Technical Assessment" },
  { key: "communication", label: "Communication" },
  { key: "followup", label: "Follow-up Questions" },
];

const DRAFT_KEY = (interviewId: string, section: string | null) =>
  `interview_notes_draft_${interviewId}_${section ?? "general"}`;

function NoteSection({
  interviewId,
  sectionKey,
  sectionLabel,
  initialNote,
  onSaved,
}: {
  interviewId: string;
  sectionKey: string | null;
  sectionLabel: string;
  initialNote?: InterviewNote;
  onSaved: (note: InterviewNote) => void;
}) {
  const [content, setContent] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(DRAFT_KEY(interviewId, sectionKey)) ?? initialNote?.content ?? "";
    }
    return initialNote?.content ?? "";
  });
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(
    initialNote?.autosaved_at ? new Date(initialNote.autosaved_at) : null,
  );
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Autosave draft to localStorage on every keystroke
  useEffect(() => {
    localStorage.setItem(DRAFT_KEY(interviewId, sectionKey), content);
  }, [content, interviewId, sectionKey]);

  const save = useCallback(
    async (finalized = false) => {
      if (!content.trim()) return;
      setSaving(true);
      try {
        const note = await upsertNote(interviewId, {
          section: sectionKey,
          content,
          finalized,
        });
        setSavedAt(new Date());
        onSaved(note);
        if (finalized) {
          localStorage.removeItem(DRAFT_KEY(interviewId, sectionKey));
        }
      } finally {
        setSaving(false);
      }
    },
    [content, interviewId, sectionKey, onSaved],
  );

  // Debounced autosave every 3 seconds
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void save(false), 3000);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">{sectionLabel}</h3>
        <div className="flex items-center gap-2">
          {savedAt && (
            <span className="text-[10px] text-gray-400">
              Saved {savedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] px-2 gap-1"
            onClick={() => void save(false)}
            disabled={saving || !content.trim()}
          >
            <Save className="w-3 h-3" />
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
      <textarea
        className="w-full rounded-lg border border-gray-200 p-3 text-sm text-gray-800 resize-none focus:outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] transition-all placeholder:text-gray-400"
        rows={5}
        placeholder={`${sectionLabel} notes…`}
        value={content}
        onChange={handleChange}
      />
    </div>
  );
}

export function NotesPanel({
  interviewId,
  initialNotes,
}: {
  interviewId: string;
  initialNotes: InterviewNote[];
}) {
  const [notes, setNotes] = useState<InterviewNote[]>(initialNotes);

  const handleSaved = useCallback((saved: InterviewNote) => {
    setNotes((prev) => {
      const idx = prev.findIndex(
        (n) => n.section === saved.section && n.interviewer_id === saved.interviewer_id,
      );
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [...prev, saved];
    });
  }, []);

  const noteFor = (key: string | null) =>
    notes.find((n) => n.section === key) ?? undefined;

  return (
    <div className="h-full overflow-y-auto space-y-5 pr-1">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-[#FF5A1F]" />
        <h2 className="text-sm font-semibold text-gray-800">Interview Notes</h2>
        <span className="text-[10px] text-gray-400 ml-auto">Auto-saves every 3s</span>
      </div>

      {SECTIONS.map(({ key, label }) => (
        <NoteSection
          key={String(key)}
          interviewId={interviewId}
          sectionKey={key}
          sectionLabel={label}
          initialNote={noteFor(key)}
          onSaved={handleSaved}
        />
      ))}
    </div>
  );
}
