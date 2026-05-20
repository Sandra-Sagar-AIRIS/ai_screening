"use client";

import { cn } from "@/lib/utils";
import type { SubmissionOutcome, VendorSubmissionStatus } from "@/lib/api/types";

// ── Outcome badge ──────────────────────────────────────────────────────────

const OUTCOME_CONFIG: Record<SubmissionOutcome, { label: string; className: string }> = {
  pending: {
    label: "Pending",
    className: "bg-slate-100 text-slate-600 border-slate-200",
  },
  accepted: {
    label: "Accepted",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  rejected: {
    label: "Rejected",
    className: "bg-red-50 text-red-600 border-red-200",
  },
};

export function SubmissionOutcomeBadge({ outcome }: { outcome: SubmissionOutcome }) {
  const config = OUTCOME_CONFIG[outcome] ?? OUTCOME_CONFIG.pending;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}

// ── Vendor status badge ────────────────────────────────────────────────────

const VENDOR_STATUS_CONFIG: Record<VendorSubmissionStatus, { label: string; className: string; dot: string }> = {
  submitted: {
    label: "Submitted",
    className: "bg-blue-50 text-blue-700 border-blue-200",
    dot: "bg-blue-500",
  },
  under_review: {
    label: "Under Review",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-400",
  },
  accepted: {
    label: "Accepted",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  rejected: {
    label: "Rejected",
    className: "bg-red-50 text-red-600 border-red-200",
    dot: "bg-red-500",
  },
};

export function VendorStatusBadge({ status }: { status: VendorSubmissionStatus }) {
  const config = VENDOR_STATUS_CONFIG[status] ?? VENDOR_STATUS_CONFIG.submitted;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
        config.className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </span>
  );
}
