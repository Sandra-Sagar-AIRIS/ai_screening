"use client";

type ATSRecommendationBadgeProps = {
  recommendation?: string | null;
  /** When true and recommendation is empty, show “Score pending…”. Default false (neutral dash). */
  awaitingMatch?: boolean;
  isLoading?: boolean;
  compact?: boolean;
  className?: string;
};

function recommendationTone(recommendation: string) {
  const normalized = recommendation.toLowerCase();
  if (normalized.includes("strong")) return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (normalized.includes("good")) return "bg-blue-50 text-blue-700 border-blue-100";
  if (normalized.includes("moderate")) return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-slate-50 text-slate-600 border-slate-100";
}

export function ATSRecommendationBadge({
  recommendation,
  awaitingMatch = false,
  isLoading,
  compact = false,
  className = "",
}: ATSRecommendationBadgeProps) {
  if (isLoading) {
    return (
      <span
        className={`inline-flex animate-pulse items-center rounded-full border px-2 py-0.5 text-xs font-medium ${compact ? "h-5 w-20" : "h-6 w-28"} ${className}`}
      />
    );
  }

  const trimmed = recommendation?.trim() ?? "";
  if (!trimmed) {
    if (awaitingMatch) {
      return (
        <span className={`inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 ${className}`}>
          Score pending…
        </span>
      );
    }
    return (
      <span className={`inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400 ${className}`}>
        —
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${recommendationTone(trimmed)} ${className}`}>
      {trimmed}
    </span>
  );
}

