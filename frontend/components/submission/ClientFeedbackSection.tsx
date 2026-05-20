"use client";

import { useState } from "react";
import { MessageSquare, Check, Loader2 } from "lucide-react";
import { updateSubmissionFeedback, updateSubmissionOutcome } from "@/lib/api/vendor";
import type { JobSubmission, SubmissionOutcome } from "@/lib/api/types";
import { SubmissionOutcomeBadge } from "./SubmissionStatusBadge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ── Outcome selector ───────────────────────────────────────────────────────

const OUTCOME_OPTIONS: { value: SubmissionOutcome; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
];

// ── Component ──────────────────────────────────────────────────────────────

interface ClientFeedbackSectionProps {
  submission: JobSubmission;
  jobId: string;
  canEdit?: boolean;
  onUpdated?: (updated: JobSubmission) => void;
}

export function ClientFeedbackSection({
  submission,
  jobId,
  canEdit = false,
  onUpdated,
}: ClientFeedbackSectionProps) {
  const [outcome, setOutcome] = useState<SubmissionOutcome>(submission.outcome);
  const [feedback, setFeedback] = useState(submission.client_feedback ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    outcome !== submission.outcome ||
    feedback !== (submission.client_feedback ?? "");

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      // Save outcome (+ feedback inline when provided).
      const updated = await updateSubmissionOutcome(jobId, submission.id, {
        outcome,
        client_feedback: feedback || undefined,
      });
      setSaved(true);
      onUpdated?.(updated);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: unknown) {
      setError(
        (err as { detail?: string; message?: string })?.detail ??
          (err as { message?: string })?.message ??
          "Failed to save.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-slate-800">Client Feedback</h3>
        <div className="ml-auto">
          <SubmissionOutcomeBadge outcome={submission.outcome} />
        </div>
      </div>

      {/* Submission meta */}
      <div className="grid grid-cols-2 gap-3 text-[12px]">
        <div>
          <p className="text-slate-400 font-medium uppercase tracking-wide text-[10px] mb-0.5">Submitted</p>
          <p className="text-slate-700">
            {new Date(submission.submitted_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        </div>
        <div>
          <p className="text-slate-400 font-medium uppercase tracking-wide text-[10px] mb-0.5">Outcome</p>
          {canEdit ? (
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as SubmissionOutcome)}
              className="h-7 rounded-md border border-slate-200 bg-white px-2 text-[12px] text-slate-700 focus:outline-none focus:border-orange-400"
              disabled={saving}
            >
              {OUTCOME_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            <SubmissionOutcomeBadge outcome={outcome} />
          )}
        </div>
      </div>

      {/* Feedback text */}
      {canEdit ? (
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">
            Client Feedback
          </label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            rows={3}
            placeholder="Record client feedback about this candidate…"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-300 focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-400 resize-none"
            disabled={saving}
          />
        </div>
      ) : submission.client_feedback ? (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-1">Client Feedback</p>
          <p className="text-sm text-slate-600 italic">&ldquo;{submission.client_feedback}&rdquo;</p>
        </div>
      ) : (
        <p className="text-xs text-slate-400 italic">No feedback recorded yet.</p>
      )}

      {/* Error */}
      {error && (
        <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      {/* Save button */}
      {canEdit && (
        <div className="flex justify-end">
          <Button
            size="sm"
            disabled={!dirty || saving}
            onClick={() => void handleSave()}
            className={cn(
              "gap-1.5",
              saved
                ? "bg-emerald-500 hover:bg-emerald-600 text-white"
                : "bg-orange-500 hover:bg-orange-600 text-white",
            )}
          >
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : saved ? (
              <Check className="h-3.5 w-3.5" />
            ) : null}
            {saving ? "Saving…" : saved ? "Saved" : "Save Feedback"}
          </Button>
        </div>
      )}
    </div>
  );
}
