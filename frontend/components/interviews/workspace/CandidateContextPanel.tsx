"use client";

import { BookOpen, Briefcase, GraduationCap, MapPin, Phone, Mail, User } from "lucide-react";
import type { CandidateWorkspaceInfo, FeedbackSummary } from "@/lib/api/types";

const SCORE_LABELS: Record<string, string> = {
  avg_technical: "Technical",
  avg_communication: "Communication",
  avg_problem_solving: "Problem Solving",
  avg_culture_fit: "Culture Fit",
  avg_system_design: "System Design",
  avg_leadership: "Leadership",
};

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  const pct = ((value - 1) / 4) * 100;
  const color = value >= 4 ? "bg-green-500" : value >= 3 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-600">
        <span>{label}</span>
        <span className="font-medium">{value.toFixed(1)}/5</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function CandidateContextPanel({
  candidate,
  jobTitle,
  feedbackSummary,
}: {
  candidate: CandidateWorkspaceInfo | null;
  jobTitle: string | null;
  feedbackSummary: FeedbackSummary | null;
}) {
  return (
    <div className="h-full overflow-y-auto space-y-4 pr-1">
      {/* Candidate identity */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-[#FF5A1F] font-bold text-sm shrink-0">
            {candidate ? `${candidate.first_name[0]}${candidate.last_name[0]}` : "?"}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 text-sm">
              {candidate ? `${candidate.first_name} ${candidate.last_name}` : "Unknown candidate"}
            </p>
            {jobTitle && (
              <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                <Briefcase className="w-3 h-3 shrink-0" />
                {jobTitle}
              </p>
            )}
          </div>
        </div>

        {candidate && (
          <div className="space-y-1.5 text-xs text-gray-600">
            {candidate.email && (
              <p className="flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                {candidate.email}
              </p>
            )}
            {candidate.phone && (
              <p className="flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                {candidate.phone}
              </p>
            )}
            {candidate.location && (
              <p className="flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                {candidate.location}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Experience summary */}
      {candidate?.experience_summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
            <User className="w-3.5 h-3.5" />
            Experience
          </h3>
          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-line">
            {candidate.experience_summary}
          </p>
        </div>
      )}

      {/* Education */}
      {candidate?.education && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
            <GraduationCap className="w-3.5 h-3.5" />
            Education
          </h3>
          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-line">
            {candidate.education}
          </p>
        </div>
      )}

      {/* Recruiter notes */}
      {candidate?.notes && (
        <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 space-y-2">
          <h3 className="text-xs font-semibold text-amber-700 uppercase tracking-wider flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            Recruiter Notes
          </h3>
          <p className="text-xs text-amber-900 leading-relaxed whitespace-pre-line">
            {candidate.notes}
          </p>
        </div>
      )}

      {/* Panel feedback summary */}
      {feedbackSummary && feedbackSummary.count > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Panel Scores ({feedbackSummary.count} {feedbackSummary.count === 1 ? "review" : "reviews"})
          </h3>
          <div className="space-y-2">
            {Object.entries(SCORE_LABELS).map(([key, label]) => (
              <ScoreBar
                key={key}
                label={label}
                value={(feedbackSummary as Record<string, number | null>)[key]}
              />
            ))}
            {feedbackSummary.avg_overall !== null && (
              <div className="pt-1 border-t border-gray-100">
                <ScoreBar label="Overall Rating" value={feedbackSummary.avg_overall} />
              </div>
            )}
          </div>

          {Object.keys(feedbackSummary.recommendations).length > 0 && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs font-medium text-gray-500 mb-1.5">Recommendations</p>
              <div className="flex flex-wrap gap-1">
                {Object.entries(feedbackSummary.recommendations).map(([rec, count]) => (
                  <span key={rec} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 capitalize">
                    {rec.replace("_", " ")} ({count})
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
