"use client";

import { useState } from "react";
import { changePipelineStatus } from "@/lib/api/pipeline";
import type { Pipeline, PipelineStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { ChevronDown, Loader2 } from "lucide-react";

// ── Status display config ──────────────────────────────────────────────────

export const STATUS_LABELS: Record<PipelineStatus, string> = {
  active: "Active",
  on_hold: "On Hold",
  withdrawn: "Withdrawn",
  closed: "Closed",
};

const STATUS_COLORS: Record<PipelineStatus, string> = {
  active: "bg-green-100 text-green-700 border-green-200",
  on_hold: "bg-yellow-100 text-yellow-700 border-yellow-200",
  withdrawn: "bg-orange-100 text-orange-700 border-orange-200",
  closed: "bg-slate-100 text-slate-600 border-slate-200",
};

export function PipelineStatusBadge({ status }: { status: PipelineStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600 border-slate-200"
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

// ── Allowed transitions map ────────────────────────────────────────────────
// (mirrors backend logic — terminal statuses show no options)

const STATUS_OPTIONS: Record<PipelineStatus, PipelineStatus[]> = {
  active: ["on_hold", "withdrawn", "closed"],
  on_hold: ["active", "withdrawn", "closed"],
  withdrawn: ["active"],    // admin re-open only (backend enforces)
  closed: ["active"],       // admin re-open only (backend enforces)
};

// ── PipelineStatusControl ─────────────────────────────────────────────────

interface PipelineStatusControlProps {
  pipeline: Pipeline;
  canEdit?: boolean;
  onStatusChanged?: (updated: Pipeline) => void;
}

export function PipelineStatusControl({
  pipeline,
  canEdit = false,
  onStatusChanged,
}: PipelineStatusControlProps) {
  const [open, setOpen] = useState(false);
  const [changing, setChanging] = useState<PipelineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const options = STATUS_OPTIONS[pipeline.status] ?? [];

  async function handleChange(newStatus: PipelineStatus) {
    setOpen(false);
    setChanging(newStatus);
    setError(null);

    try {
      const updated = await changePipelineStatus(pipeline.id, { status: newStatus });
      onStatusChanged?.(updated);
    } catch (err: unknown) {
      const detail =
        (err as { detail?: string; message?: string })?.detail ??
        (err as { message?: string })?.message ??
        "Failed to update status.";
      setError(detail);
    } finally {
      setChanging(null);
    }
  }

  if (!canEdit || options.length === 0) {
    return (
      <div className="flex items-center gap-2">
        <PipelineStatusBadge status={pipeline.status} />
        {error && <span className="text-xs text-red-500">{error}</span>}
      </div>
    );
  }

  return (
    <div className="relative inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={!!changing}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors hover:opacity-80",
          STATUS_COLORS[pipeline.status] ?? "bg-slate-100 text-slate-600 border-slate-200"
        )}
      >
        {changing ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>{STATUS_LABELS[changing]}…</span>
          </>
        ) : (
          <>
            {STATUS_LABELS[pipeline.status] ?? pipeline.status}
            <ChevronDown className="h-3 w-3" />
          </>
        )}
      </button>

      {open && (
        <>
          {/* backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 top-full z-20 mt-1 min-w-[140px] rounded-xl bg-white border border-slate-200 shadow-lg py-1 overflow-hidden">
            {options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => handleChange(opt)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <span
                  className={cn(
                    "inline-block h-2 w-2 rounded-full",
                    opt === "active" ? "bg-green-500" :
                    opt === "on_hold" ? "bg-yellow-400" :
                    opt === "withdrawn" ? "bg-orange-500" :
                    "bg-slate-400"
                  )}
                />
                {STATUS_LABELS[opt]}
              </button>
            ))}
          </div>
        </>
      )}

      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
