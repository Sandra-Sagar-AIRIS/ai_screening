"use client";

/**
 * PIPE-008: Decline Reason Modal
 *
 * Collects a mandatory decline reason (≥ 10 chars) and an optional flag to
 * revert the candidate to their previous stage instead of marking as rejected.
 */

import { useRef, useState } from "react";
import { XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const MIN_REASON_LEN = 10;

export interface DeclineReasonResult {
  decline_reason: string;
  revert_to_previous_stage: boolean;
}

type Props = {
  candidateName?: string;
  previousStage?: string | null;
  onConfirm: (result: DeclineReasonResult) => void;
  onCancel: () => void;
  submitting?: boolean;
};

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  screening: "Screening",
  ai_screening: "AI Screening",
  interview: "Interview",
  offer: "Offer",
};

export function DeclineReasonModal({
  candidateName,
  previousStage,
  onConfirm,
  onCancel,
  submitting = false,
}: Props) {
  const [reason, setReason] = useState("");
  const [revert, setRevert] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const remaining = Math.max(0, MIN_REASON_LEN - reason.trim().length);
  const canSubmit = reason.trim().length >= MIN_REASON_LEN && !submitting;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    onConfirm({ decline_reason: reason.trim(), revert_to_previous_stage: revert });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="relative w-full max-w-md rounded-2xl bg-white shadow-2xl p-6">
        {/* Close */}
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="absolute top-3 right-3 text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50"
          aria-label="Close"
        >
          <XCircle className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3 mb-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 shrink-0">
            <XCircle className="h-5 w-5 text-red-500" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Decline Offer</h2>
            {candidateName && (
              <p className="text-sm text-slate-500 mt-0.5">{candidateName}</p>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Reason */}
          <div>
            <label
              htmlFor="decline-reason"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              Decline reason <span className="text-red-500">*</span>
            </label>
            <textarea
              id="decline-reason"
              ref={textareaRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Describe why this offer is being declined…"
              rows={4}
              disabled={submitting}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-400 disabled:opacity-50 resize-none"
            />
            {remaining > 0 && (
              <p className="mt-1 text-xs text-slate-400">
                {remaining} more character{remaining !== 1 ? "s" : ""} required
              </p>
            )}
          </div>

          {/* Revert option — only shown when a previous stage is known */}
          {previousStage && previousStage !== "applied" && (
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={revert}
                onChange={(e) => setRevert(e.target.checked)}
                disabled={submitting}
                className="mt-0.5 accent-orange-500"
              />
              <div>
                <span className="text-sm font-medium text-slate-700">
                  Return to {STAGE_LABELS[previousStage] ?? previousStage} stage
                </span>
                <p className="text-xs text-slate-400">
                  Uncheck to move directly to Rejected.
                </p>
              </div>
            </label>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  Declining…
                </>
              ) : (
                "Confirm Decline"
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
