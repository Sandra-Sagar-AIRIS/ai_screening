"use client";

/**
 * RejectCandidateModal
 *
 * Collects a mandatory rejection reason (≥ 10 chars) before transitioning
 * a candidate pipeline to the "rejected" stage via PIPE-002 transition endpoint.
 */

import { useRef, useState } from "react";
import { XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { transitionPipelineStage } from "@/lib/api/pipeline";
import { ApiError } from "@/lib/api/client";
import type { Pipeline } from "@/lib/api/types";

const MIN_REASON_LEN = 10;

type Props = {
  pipeline: Pipeline;
  candidateName?: string;
  onSuccess: (updated: Pipeline) => void;
  onCancel: () => void;
};

export function RejectCandidateModal({ pipeline, candidateName, onSuccess, onCancel }: Props) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const remaining = Math.max(0, MIN_REASON_LEN - reason.trim().length);
  const canSubmit = reason.trim().length >= MIN_REASON_LEN && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await transitionPipelineStage(pipeline.id, {
        stage: "rejected",
        reason: reason.trim(),
      });
      onSuccess(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reject candidate.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="relative w-full max-w-md rounded-xl bg-white dark:bg-gray-900 shadow-2xl p-6">
        {/* Close */}
        <button
          type="button"
          onClick={onCancel}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
          aria-label="Close"
        >
          <XCircle className="h-5 w-5" />
        </button>

        <div className="flex items-start gap-3 mb-4">
          <XCircle className="h-6 w-6 text-red-500 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Reject Candidate
            </h2>
            {candidateName && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {candidateName}
              </p>
            )}
          </div>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label
              htmlFor="rejection-reason"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Rejection reason
              <span className="text-red-500 ml-0.5">*</span>
            </label>
            <textarea
              id="rejection-reason"
              ref={textareaRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Describe why this candidate is being rejected…"
              rows={4}
              disabled={submitting}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-red-400 disabled:opacity-50 resize-none"
            />
            {remaining > 0 && (
              <p className="mt-1 text-xs text-gray-400">
                {remaining} more character{remaining !== 1 ? "s" : ""} required
              </p>
            )}
          </div>

          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
            >
              {submitting ? "Rejecting…" : "Confirm Rejection"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
