"use client";

import { useEffect, useState } from "react";
import { getPipelineStatusHistory } from "@/lib/api/pipeline";
import type { PipelineStatusHistory } from "@/lib/api/types";
import { cn } from "@/lib/utils";

// ── Status display config ──────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  on_hold: "On Hold",
  withdrawn: "Withdrawn",
  closed: "Closed",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  on_hold: "bg-yellow-100 text-yellow-700",
  withdrawn: "bg-orange-100 text-orange-700",
  closed: "bg-slate-100 text-slate-600",
};

function StatusChip({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
        STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function formatTs(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// ── Panel component ────────────────────────────────────────────────────────

interface PipelineStatusHistoryPanelProps {
  pipelineId: string;
  /** Re-fetch trigger: increment to force a refresh (e.g. after a status change). */
  refreshKey?: number;
}

export function PipelineStatusHistoryPanel({
  pipelineId,
  refreshKey = 0,
}: PipelineStatusHistoryPanelProps) {
  const [history, setHistory] = useState<PipelineStatusHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getPipelineStatusHistory(pipelineId)
      .then((data) => {
        if (!cancelled) {
          // Show newest first in the UI.
          setHistory([...data].reverse());
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError((err as { message?: string })?.message ?? "Failed to load status history.");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [pipelineId, refreshKey]);

  if (loading) {
    return (
      <div className="py-6 text-center text-sm text-slate-400">
        Loading status history…
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4 text-center text-sm text-red-500">{error}</div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-slate-400">
        No status changes recorded yet.
      </div>
    );
  }

  return (
    <ol className="relative ml-3 border-l border-slate-200 space-y-5">
      {history.map((entry) => (
        <li key={entry.id} className="ml-5">
          {/* Timeline dot */}
          <span className="absolute -left-[7px] flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white border-2 border-orange-400" />

          <div className="flex flex-wrap items-center gap-2">
            {entry.previous_status ? (
              <>
                <StatusChip status={entry.previous_status} />
                <span className="text-slate-400 text-xs">→</span>
              </>
            ) : null}
            <StatusChip status={entry.new_status} />
            <span className="text-[11px] text-slate-400 ml-auto">
              {formatTs(entry.changed_at)}
            </span>
          </div>

          {entry.reason && (
            <p className="mt-1 text-xs text-slate-500 italic">&ldquo;{entry.reason}&rdquo;</p>
          )}
        </li>
      ))}
    </ol>
  );
}
