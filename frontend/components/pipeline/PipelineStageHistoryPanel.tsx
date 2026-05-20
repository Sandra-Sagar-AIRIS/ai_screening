"use client";

/**
 * PipelineStageHistoryPanel
 *
 * Shows the full stage-transition audit log for a single pipeline record.
 * Fetches from GET /pipelines/{id}/history (PIPE-002).
 */

import { useEffect, useState } from "react";
import { CheckCircle, ChevronDown, ChevronUp, Clock, XCircle } from "lucide-react";
import { getPipelineStageHistory } from "@/lib/api/pipeline";
import type { PipelineStageHistory } from "@/lib/api/types";

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  screening: "Screening",
  ai_screening: "AI Screening",
  interview: "Interview",
  offer: "Offer",
  placed: "Placed",
  rejected: "Rejected",
};

const STAGE_COLOR: Record<string, string> = {
  applied: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300",
  screening: "bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300",
  ai_screening: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  interview: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  offer: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  placed: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

function StageBadge({ stage }: { stage: string }) {
  const color = STAGE_COLOR[stage] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

type Props = {
  pipelineId: string;
  /** If false, the panel starts collapsed and requires a click to expand. */
  defaultExpanded?: boolean;
};

export function PipelineStageHistoryPanel({ pipelineId, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [history, setHistory] = useState<PipelineStageHistory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    setError(null);
    getPipelineStageHistory(pipelineId)
      .then(setHistory)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load history.");
      })
      .finally(() => setLoading(false));
  }, [pipelineId, expanded]);

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
      {/* Header / toggle */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors"
      >
        <span className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-400" />
          Stage History
          {history.length > 0 && (
            <span className="ml-1 rounded-full bg-gray-100 dark:bg-gray-700 px-2 py-0.5 text-xs font-semibold text-gray-600 dark:text-gray-300">
              {history.length}
            </span>
          )}
        </span>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 px-4 py-3">
          {loading && (
            <p className="text-xs text-gray-400 animate-pulse">Loading history…</p>
          )}

          {error && (
            <p className="text-xs text-red-500">{error}</p>
          )}

          {!loading && !error && history.length === 0 && (
            <p className="text-xs text-gray-400">No stage transitions recorded yet.</p>
          )}

          {!loading && !error && history.length > 0 && (
            <ol className="relative space-y-0">
              {history.map((row, i) => {
                const isRejection = row.new_stage === "rejected";
                const isLast = i === history.length - 1;

                return (
                  <li key={row.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {/* Timeline spine */}
                    {!isLast && (
                      <div className="absolute left-[9px] top-5 bottom-0 w-px bg-gray-200 dark:bg-gray-700" />
                    )}

                    {/* Dot */}
                    <div className="mt-1 shrink-0">
                      {isRejection ? (
                        <XCircle className="h-5 w-5 text-red-400" />
                      ) : (
                        <CheckCircle className="h-5 w-5 text-emerald-400" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5 text-sm">
                        {row.previous_stage ? (
                          <>
                            <StageBadge stage={row.previous_stage} />
                            <span className="text-gray-400">→</span>
                          </>
                        ) : null}
                        <StageBadge stage={row.new_stage} />
                      </div>

                      {row.reason && (
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 italic">
                          &ldquo;{row.reason}&rdquo;
                        </p>
                      )}

                      <p className="mt-0.5 text-xs text-gray-400">
                        {formatDate(row.transitioned_at)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
