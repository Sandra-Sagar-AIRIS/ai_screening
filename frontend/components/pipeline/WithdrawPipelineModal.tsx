"use client";

import { useState } from "react";
import { withdrawPipeline } from "@/lib/api/pipeline";
import { X, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Pipeline } from "@/lib/api/types";

interface WithdrawPipelineModalProps {
  pipeline: Pipeline;
  candidateName?: string;
  onClose: () => void;
  onWithdrawn: (updated: Pipeline) => void;
}

export function WithdrawPipelineModal({
  pipeline,
  candidateName,
  onClose,
  onWithdrawn,
}: WithdrawPipelineModalProps) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = reason.trim().length >= 5 && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setError(null);

    try {
      const updated = await withdrawPipeline(pipeline.id, { reason: reason.trim() });
      onWithdrawn(updated);
    } catch (err: unknown) {
      const detail = (err as { detail?: string; message?: string })?.detail
        ?? (err as { message?: string })?.message
        ?? "Failed to withdraw pipeline.";
      setError(detail);
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md rounded-2xl bg-white shadow-2xl p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-50">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Withdraw Application</h2>
              {candidateName && (
                <p className="text-sm text-slate-500">{candidateName}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-sm text-slate-600 mb-4">
          This will mark the pipeline as <strong>withdrawn</strong> and record an audit entry.
          The candidate will no longer appear as an active applicant.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="withdraw-reason"
              className="block text-sm font-medium text-slate-700 mb-1.5"
            >
              Reason <span className="text-slate-400 font-normal">(required, ≥ 5 characters)</span>
            </label>
            <textarea
              id="withdraw-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="e.g. Candidate accepted another offer, withdrew from process…"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-400 resize-none"
              disabled={submitting}
            />
            <p className="mt-1 text-[11px] text-slate-400">
              {reason.trim().length} / 5 min characters
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <div className="flex gap-3 justify-end pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-orange-500 hover:bg-orange-600 text-white"
            >
              {submitting ? "Withdrawing…" : "Withdraw Application"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
