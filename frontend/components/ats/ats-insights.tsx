"use client";

import React, { useState } from "react";
import { 
  CheckCircle2, 
  XCircle, 
  Info, 
  Brain, 
  Target, 
  Sparkles, 
  Zap, 
  Briefcase, 
  GraduationCap, 
  MapPin, 
  MessageSquare, 
  Users, 
  Search,
  RotateCw,
  ChevronRight,
  TrendingUp,
  AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type MatchBreakdownData = {
  fit_score?: number | null;
  deterministic_match_score?: number | null;
  semantic_match_score?: number | null;
  ai_enrichment_status?: string | null;
  ats_pipeline_status?: string | null;
  enrichment_error?: string | null;
  deterministic_completed_at?: string | null;
  semantic_completed_at?: string | null;
  recommendation?: string | null;
  confidence_score?: number | null;
  confidence_reasoning?: string | null;
  recruiter_summary?: string | null;
  semantic_skill_matches?: string[];
  transferable_skills?: string[];
  inferred_strengths?: string[];
  inferred_gaps?: string[];
  category_scores?: {
    required_skills?: number;
    preferred_skills?: number;
    experience?: number;
    title?: number;
    education?: number;
    hybrid?: {
      deterministic_score?: number;
      semantic_score?: number | null;
      final_score?: number;
      weights?: { deterministic?: number; semantic?: number };
    };
  } | null;
  matched_skills?: string[];
  missing_skills?: string[];
  evaluated_at?: string | null;
};

interface ATSInsightsProps {
  data: MatchBreakdownData;
  jobTitle: string;
  candidateName: string;
  executiveSummary?: string | null;
  isLoading?: boolean;
  onRescore: () => void;
  rescoreBusy?: boolean;
}

const CircularProgress = ({ value, size = 96, strokeWidth = 8, color = "#FF5A1F" }: { value: number; size?: number; strokeWidth?: number; color?: string }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90 overflow-visible">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#E2E8F0"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          style={{
            strokeDashoffset: offset,
            transition: "stroke-dashoffset 0.8s ease-in-out",
          }}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{Math.round(value)}<span className="text-sm">%</span></span>
      </div>
    </div>
  );
};

const SmallCircularProgress = ({ value, color = "#FF5A1F" }: { value: number; color?: string }) => {
  const size = 36;
  const strokeWidth = 3;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90 overflow-visible">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#E2E8F0"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          style={{
            strokeDashoffset: offset,
            transition: "stroke-dashoffset 0.8s ease-in-out",
          }}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-[10px] font-bold text-slate-700">{Math.round(value)}%</span>
    </div>
  );
};

/* ─────────────────────────────────────────────
   Executive Summary Card — collapsible, animated
   ───────────────────────────────────────────── */
const ExecutiveSummaryCard = ({
  summary,
  confidenceReasoning,
}: {
  summary: string;
  confidenceReasoning?: string | null;
}) => {
  const [expanded, setExpanded] = useState(false);

  // Only show the toggle if text is long enough to overflow 3 lines
  const CHAR_THRESHOLD = 180;
  const needsToggle = summary.length > CHAR_THRESHOLD;

  return (
    <div className="bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-2xl p-4 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <p className="font-bold text-slate-900 flex items-center gap-1.5 text-sm">
          <span className="w-6 h-6 rounded-lg bg-orange-100 flex items-center justify-center shrink-0">
            <Brain className="w-3.5 h-3.5 text-[#FF5A1F]" />
          </span>
          Executive Summary
        </p>
        {needsToggle && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-[11px] font-bold text-[#FF5A1F] hover:text-orange-600 transition-colors px-2 py-0.5 rounded-lg hover:bg-orange-50 shrink-0"
            aria-expanded={expanded}
          >
            {expanded ? "Show less" : "Show more"}
            <ChevronRight
              className={`w-3.5 h-3.5 transition-transform duration-300 ${
                expanded ? "rotate-[270deg]" : "rotate-90"
              }`}
            />
          </button>
        )}
      </div>

      {/* Body with smooth height animation */}
      <div
        className="overflow-hidden transition-all duration-500 ease-in-out"
        style={{ maxHeight: expanded ? "1200px" : "4.8em" }}
      >
        <p
          className="text-[13px] text-slate-700 leading-relaxed break-words whitespace-pre-wrap"
          style={
            expanded
              ? {}
              : {
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }
          }
        >
          {summary}
        </p>

        {/* Confidence reasoning — only visible when expanded */}
        {expanded && confidenceReasoning && (
          <p className="mt-3 text-xs italic text-slate-500 border-t border-slate-200 pt-2 break-words whitespace-pre-wrap leading-relaxed">
            {confidenceReasoning}
          </p>
        )}
      </div>

      {/* Fade-out gradient when collapsed */}
      {needsToggle && !expanded && (
        <div
          className="pointer-events-none -mt-6 h-6 w-full rounded-b-2xl"
          style={{
            background:
              "linear-gradient(to bottom, transparent, rgba(248,250,252,0.95))",
          }}
        />
      )}
    </div>
  );
};

export const ATSInsights = ({ data, jobTitle, candidateName, executiveSummary, isLoading, onRescore, rescoreBusy }: ATSInsightsProps) => {
  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-[200px] bg-slate-100 rounded-2xl w-full" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-24 bg-slate-100 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const score = data.fit_score ?? 0;
  const recommendation = data.recommendation || "Needs Review";
  
  const getScoreColor = (s: number) => {
    return "#FF5A1F"; // Brand orange
  };

  const getScoreTone = (s: number) => {
    return "bg-orange-50 text-[#FF5A1F] border-orange-100";
  };

  const categories = [
    { label: "Required Skills", value: data.category_scores?.required_skills ?? 0, icon: Target, color: "#10B981", iconClass: "text-emerald-500 bg-emerald-50 group-hover:bg-emerald-100" },
    { label: "Preferred Skills", value: data.category_scores?.preferred_skills ?? 0, icon: Sparkles, color: "#10B981", iconClass: "text-emerald-500 bg-emerald-50 group-hover:bg-emerald-100" },
    { label: "Experience", value: data.category_scores?.experience ?? 0, icon: Briefcase, color: "#8B5CF6", iconClass: "text-violet-500 bg-violet-50 group-hover:bg-violet-100" },
    { label: "Title Alignment", value: data.category_scores?.title ?? 0, icon: Users, color: "#8B5CF6", iconClass: "text-violet-500 bg-violet-50 group-hover:bg-violet-100" },
    { label: "Education", value: data.category_scores?.education ?? 0, icon: GraduationCap, color: "#3B82F6", iconClass: "text-blue-500 bg-blue-50 group-hover:bg-blue-100" },
    { label: "Location", value: data.category_scores?.title ? 100 : 0, icon: MapPin, color: "#3B82F6", iconClass: "text-blue-500 bg-blue-50 group-hover:bg-blue-100" }, 
    { label: "Communication Fit", value: data.confidence_score ? Math.round(data.confidence_score * 100) : 70, icon: MessageSquare, status: data.confidence_score ? (data.confidence_score > 0.7 ? "High" : "Medium") : "Not evaluated", color: "#F59E0B", iconClass: "text-amber-500 bg-amber-50 group-hover:bg-amber-100" },
    { label: "Culture Fit", value: data.fit_score ?? 75, icon: Users, status: "Analyzed", color: "#F59E0B", iconClass: "text-amber-500 bg-amber-50 group-hover:bg-amber-100" },
  ];

  return (
    <div className="space-y-8 pb-8">
      {/* Top Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 md:p-6 flex flex-col md:flex-row gap-6 items-start">
          {/* Left: Score Circle */}
          <div className="flex flex-col items-center gap-3 shrink-0">
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">ATS Match Score</h3>
            <CircularProgress value={score} color={getScoreColor(score)} />
            <div className={cn("px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest border", getScoreTone(score))}>
              {recommendation}
            </div>
          </div>

          {/* Right: Summary and Stats */}
          <div className="flex-1 min-w-0 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2 min-w-0">
                <h2 className="text-xl font-extrabold text-slate-900 truncate">{jobTitle}</h2>
                <span className="px-2 py-0.5 bg-slate-100 text-slate-700 text-[10px] font-bold uppercase rounded-md flex items-center gap-1 border border-slate-200 shrink-0">
                  <Brain className="w-3 h-3" /> AI Powered
                </span>
              </div>
              <Button 
                variant="outline" 
                onClick={onRescore} 
                disabled={rescoreBusy}
                className="rounded-lg border-slate-200 text-slate-600 font-bold text-xs h-8 px-3 hover:bg-slate-50 transition-all shrink-0"
              >
                <RotateCw className={cn("w-3 h-3 mr-1.5", rescoreBusy && "animate-spin")} />
                {rescoreBusy ? "Rescoring..." : "Rescore ATS"}
              </Button>
            </div>

            {(data.recruiter_summary || executiveSummary) && (
              <ExecutiveSummaryCard
                summary={data.recruiter_summary || executiveSummary || ""}
                confidenceReasoning={data.confidence_reasoning}
              />
            )}

            <div className="space-y-1.5">
              <h4 className="text-[15px] font-bold text-slate-900">
                {score < 40 ? "Low compatibility detected" : score < 75 ? "Moderate compatibility detected" : "High compatibility detected"}
              </h4>
              <p className="text-[13px] text-slate-500 leading-relaxed max-w-2xl">
                Analysis indicates that {candidateName} has {score}% alignment with the requirements for the {jobTitle} role.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2.5 bg-white border border-slate-200 px-3.5 py-2.5 rounded-xl shadow-sm">
                <div className="w-7 h-7 rounded-full bg-slate-50 flex items-center justify-center text-slate-500">
                  <AlertCircle className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="text-base font-extrabold text-slate-900 leading-none">{(data.missing_skills?.length ?? 0)}</div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">Critical skills missing</div>
                </div>
              </div>
              <div className="flex items-center gap-2.5 bg-white border border-slate-200 px-3.5 py-2.5 rounded-xl shadow-sm">
                <div className="w-7 h-7 rounded-full bg-slate-50 flex items-center justify-center text-slate-500">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="text-base font-extrabold text-slate-900 leading-none">{data.category_scores?.required_skills ?? 0}%</div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">Required skills matched</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Match Breakdown Grid */}
      <div className="space-y-3">
        <h3 className="text-base font-bold text-slate-900 ml-1">
          Match Breakdown
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {categories.map((cat, i) => (
            <div key={i} className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between gap-2 hover:shadow-md hover:border-slate-300 transition-all group">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-bold text-slate-900 leading-tight truncate">{cat.label}</div>
                <div className="text-[11px] font-medium text-slate-500 truncate">{cat.status || "Matched"}</div>
              </div>
              <SmallCircularProgress value={cat.value} color={cat.color} />
            </div>
          ))}
        </div>
      </div>

      {/* Skill Intelligence */}
      <div className="space-y-3">
        <h3 className="text-base font-bold text-slate-900 ml-1">Skill Intelligence</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Matched Skills */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-700">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">Matched Skills ({data.matched_skills?.length ?? 0})</span>
            </div>
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {data.matched_skills?.map(skill => (
                <div key={skill} className="bg-white text-slate-700 px-4 py-2.5 rounded-lg text-xs font-semibold border border-slate-200 shadow-sm">
                  {skill}
                </div>
              ))}
            </div>
          </div>

          {/* Missing - Critical */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-700">
              <AlertCircle className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">Missing - Critical ({data.missing_skills?.length ?? 0})</span>
            </div>
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {data.missing_skills?.map(skill => (
                <div key={skill} className="bg-white text-slate-700 px-4 py-2.5 rounded-lg text-xs font-semibold border border-slate-200 shadow-sm">
                  {skill}
                </div>
              ))}
            </div>
          </div>
        </div>

        {((data.semantic_skill_matches?.length ?? 0) > 0 || (data.transferable_skills?.length ?? 0) > 0 || (data.inferred_strengths?.length ?? 0) > 0 || (data.inferred_gaps?.length ?? 0) > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
            {/* Semantic & Transferable */}
            <div className="space-y-4">
              {(data.semantic_skill_matches?.length ?? 0) > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-slate-700">
                    <Zap className="w-4 h-4 text-violet-500" />
                    <span className="text-xs font-bold uppercase tracking-wider">Semantic Skill Matches</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {data.semantic_skill_matches?.map(skill => (
                      <div key={skill} className="bg-violet-50 text-violet-700 px-3 py-1.5 rounded-md text-xs font-semibold border border-violet-200">
                        {skill}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(data.transferable_skills?.length ?? 0) > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-slate-700">
                    <RotateCw className="w-4 h-4 text-sky-500" />
                    <span className="text-xs font-bold uppercase tracking-wider">Transferable Skills</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {data.transferable_skills?.map(skill => (
                      <div key={skill} className="bg-sky-50 text-sky-700 px-3 py-1.5 rounded-md text-xs font-semibold border border-sky-200">
                        {skill}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Inferred Strengths & Gaps */}
            <div className="space-y-4">
              {(data.inferred_strengths?.length ?? 0) > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-slate-700">
                    <TrendingUp className="w-4 h-4 text-emerald-500" />
                    <span className="text-xs font-bold uppercase tracking-wider">Inferred Strengths</span>
                  </div>
                  <ul className="space-y-2">
                    {data.inferred_strengths?.map((item, i) => (
                      <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                        <span className="text-emerald-500 mt-0.5">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(data.inferred_gaps?.length ?? 0) > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-slate-700">
                    <TrendingUp className="w-4 h-4 text-rose-500 transform rotate-180" />
                    <span className="text-xs font-bold uppercase tracking-wider">Inferred Gaps</span>
                  </div>
                  <ul className="space-y-2">
                    {data.inferred_gaps?.map((item, i) => (
                      <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                        <span className="text-rose-500 mt-0.5">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
