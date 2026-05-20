"use client";

import { useRouter } from "next/navigation";
import type { DuplicateMatch } from "@/lib/api/candidate-dedup";
import { cn } from "@/lib/utils";

interface DuplicateAlertProps {
  matches: DuplicateMatch[];
  onCancel: () => void;
  onContinue: () => void;
}

const CONFIDENCE_LABELS: Record<string, { label: string; classes: string }> = {
  email: { label: "Exact email", classes: "bg-red-100 text-red-700" },
  phone: { label: "Same phone", classes: "bg-orange-100 text-orange-700" },
};

function ConfidenceBadge({ matchType }: { matchType: string }) {
  const config = CONFIDENCE_LABELS[matchType] ?? {
    label: "Possible match",
    classes: "bg-slate-100 text-slate-600",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", config.classes)}>
      {config.label}
    </span>
  );
}

function Initials({ firstName, lastName }: { firstName: string; lastName: string }) {
  const initials = `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  return (
    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-orange-100 text-sm font-bold text-[#FF5A1F]">
      {initials}
    </div>
  );
}

export function DuplicateAlert({ matches, onCancel, onContinue }: DuplicateAlertProps) {
  const router = useRouter();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dup-alert-title"
    >
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl ring-1 ring-slate-200 mx-4">
        {/* Header */}
        <div className="border-b border-slate-100 px-6 py-5">
          <h2 id="dup-alert-title" className="text-base font-semibold text-slate-900">
            Duplicate Candidate Detected
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {matches.length === 1
              ? "A candidate with matching contact details already exists."
              : `${matches.length} existing candidates may match these contact details.`}
          </p>
        </div>

        {/* Match list */}
        <ul className="divide-y divide-slate-100 max-h-64 overflow-y-auto px-6">
          {matches.map((m) => (
            <li key={m.candidate_id} className="flex items-start gap-4 py-4">
              <Initials firstName={m.first_name} lastName={m.last_name} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-900">
                    {m.first_name} {m.last_name}
                  </span>
                  <ConfidenceBadge matchType={m.match_type} />
                </div>
                <p className="mt-0.5 text-sm text-slate-500 truncate">{m.email}</p>
                {m.phone && (
                  <p className="text-xs text-slate-400">{m.phone}</p>
                )}
                {m.location && (
                  <p className="text-xs text-slate-400">{m.location}</p>
                )}
                {m.pipeline_count > 0 && (
                  <p className="mt-1 text-xs text-slate-400">
                    In {m.pipeline_count} pipeline{m.pipeline_count !== 1 ? "s" : ""}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => router.push(`/candidates/${m.candidate_id}`)}
                className="flex-shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                View
              </button>
            </li>
          ))}
        </ul>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onContinue}
            className="rounded-lg bg-[#FF5A1F] px-4 py-2 text-sm font-medium text-white hover:bg-orange-600 transition-colors"
          >
            Continue Anyway
          </button>
        </div>
      </div>
    </div>
  );
}
