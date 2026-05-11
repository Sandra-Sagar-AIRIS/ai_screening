"use client";

type ATSScoreBadgeProps = {
  score?: number | null;
  isLoading?: boolean;
  /** Pipeline / job-candidate row exists but match API has not returned a row yet (async rescore). */
  scorePending?: boolean;
  compact?: boolean;
  className?: string;
};

function scoreTone(score: number) {
  if (score >= 85) return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (score >= 70) return "bg-blue-100 text-blue-700 border-blue-200";
  if (score >= 50) return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-rose-100 text-rose-700 border-rose-200";
}

export function ATSScoreBadge({
  score,
  isLoading,
  scorePending = false,
  compact = false,
  className = "",
}: ATSScoreBadgeProps) {
  if (isLoading) {
    return (
      <span
        className={`inline-flex animate-pulse items-center rounded-full border px-2 py-0.5 text-xs font-medium ${compact ? "h-5 w-16" : "h-6 w-24"} ${className}`}
      />
    );
  }

  if (score === null || score === undefined) {
    if (scorePending) {
      return (
        <span
          className={`inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ${className}`}
          title="ATS score is generated asynchronously — refresh shortly"
        >
          Score pending
        </span>
      );
    }
    return (
      <span className={`inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 ${className}`}>
        No ATS data
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${scoreTone(score)} ${className}`}>
      {score}%
    </span>
  );
}

