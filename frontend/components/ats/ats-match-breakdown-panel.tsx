"use client";

import { ATSRecommendationBadge } from "@/components/ats/ats-recommendation-badge";
import { ATSScoreBadge } from "@/components/ats/ats-score-badge";

type MatchBreakdownData = {
  fit_score?: number | null;
  recommendation?: string | null;
  confidence_score?: number | null;
  category_scores?: {
    required_skills?: number;
    preferred_skills?: number;
    experience?: number;
    title?: number;
    education?: number;
  } | null;
  matched_skills?: string[];
  missing_skills?: string[];
  evaluated_at?: string | null;
};

type ATSMatchBreakdownPanelProps = {
  data?: MatchBreakdownData | null;
  title?: string;
  isLoading?: boolean;
};

function SkillTags({ values, tone }: { values?: string[]; tone: "match" | "missing" }) {
  if (!values?.length) return <p className="text-xs text-slate-500">-</p>;
  const cls =
    tone === "match"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : "bg-rose-50 text-rose-700 border-rose-200";
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.slice(0, 12).map((skill) => (
        <span key={skill} className={`rounded-full border px-2 py-0.5 text-[11px] ${cls}`}>
          {skill}
        </span>
      ))}
    </div>
  );
}

function ProgressRow({ label, value }: { label: string; value?: number }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-800">{pct}%</span>
      </div>
      <div className="h-1.5 rounded bg-slate-100">
        <div className="h-1.5 rounded bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ATSMatchBreakdownPanel({ data, title = "ATS Breakdown", isLoading }: ATSMatchBreakdownPanelProps) {
  if (isLoading) {
    return <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500">Processing ATS...</div>;
  }
  if (!data) {
    return <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500">ATS unavailable.</div>;
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <ATSScoreBadge score={data.fit_score} />
        <ATSRecommendationBadge recommendation={data.recommendation} />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <ProgressRow label="Required Skills" value={data.category_scores?.required_skills} />
        <ProgressRow label="Preferred Skills" value={data.category_scores?.preferred_skills} />
        <ProgressRow label="Experience" value={data.category_scores?.experience} />
        <ProgressRow label="Title Alignment" value={data.category_scores?.title} />
        <ProgressRow label="Education" value={data.category_scores?.education} />
      </div>

      <div className="mt-4 space-y-3">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Matched Skills</p>
          <SkillTags values={data.matched_skills} tone="match" />
        </div>
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">Missing Skills</p>
          <SkillTags values={data.missing_skills} tone="missing" />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>Confidence: {typeof data.confidence_score === "number" ? `${Math.round(data.confidence_score * 100)}%` : "-"}</span>
        <span>Evaluated: {data.evaluated_at ? new Date(data.evaluated_at).toLocaleString() : "-"}</span>
      </div>
    </div>
  );
}

