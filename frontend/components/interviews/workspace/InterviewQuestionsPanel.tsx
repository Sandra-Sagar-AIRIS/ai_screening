"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, RefreshCw, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getJobById } from "@/lib/api/jobs";
import { generateInterviewQuestions } from "@/lib/api/ai_interview_questions";
import type { InterviewQuestion, GenerateQuestionsResponse } from "@/lib/api/types";

const CATEGORY_LABELS: Record<string, string> = {
  technical: "Technical",
  behavioural: "Behavioural",
  situational: "Situational",
};

const CATEGORY_COLORS: Record<string, string> = {
  technical: "bg-blue-100 text-blue-800",
  behavioural: "bg-purple-100 text-purple-800",
  situational: "bg-amber-100 text-amber-800",
};

function QuestionCard({ question, index }: { question: InterviewQuestion; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="mt-0.5 shrink-0 text-gray-400">
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                CATEGORY_COLORS[question.category] ?? "bg-gray-100 text-gray-700"
              }`}
            >
              {CATEGORY_LABELS[question.category] ?? question.category}
            </span>
          </div>
          <p className="text-sm text-gray-800 leading-snug">{question.question_text}</p>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-3 border-t border-gray-100 bg-gray-50 space-y-3">
          {question.follow_up_probe && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1">
                Follow-up probe
              </p>
              <p className="text-xs text-gray-700 italic">{question.follow_up_probe}</p>
            </div>
          )}
          {question.ideal_answer_traits.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
                Good answer looks like
              </p>
              <ul className="space-y-0.5">
                {question.ideal_answer_traits.map((trait, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-gray-700">
                    <span className="mt-1 w-1 h-1 rounded-full bg-[#FF5A1F] shrink-0" />
                    {trait}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function InterviewQuestionsPanel({
  jobId,
  jobTitle,
}: {
  jobId: string | null;
  jobTitle: string | null;
}) {
  const [jobDescription, setJobDescription] = useState<string | null>(null);
  const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
  const [jobLoading, setJobLoading] = useState(false);
  const [result, setResult] = useState<GenerateQuestionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lazy-load job details the first time this panel is mounted
  useEffect(() => {
    if (!jobId) return;
    setJobLoading(true);
    getJobById(jobId)
      .then((job) => {
        setJobDescription(job.description ?? null);
        setRequiredSkills(job.required_skills ?? []);
      })
      .catch(() => {
        // Non-fatal: panel will show "no context" state
      })
      .finally(() => setJobLoading(false));
  }, [jobId]);

  const canGenerate =
    !jobLoading &&
    (jobTitle?.trim() ?? "") !== "" &&
    (jobDescription?.trim() ?? "") !== "" &&
    requiredSkills.length > 0;

  async function handleGenerate() {
    if (!canGenerate) return;
    setLoading(true);
    setError(null);
    try {
      const res = await generateInterviewQuestions({
        job_title: jobTitle!.trim(),
        job_description: jobDescription!.trim(),
        required_skills: requiredSkills,
      });
      setResult(res);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to generate questions. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  // Loading job context
  if (jobLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
        <p className="text-xs text-gray-400">Loading job details…</p>
      </div>
    );
  }

  // No job linked to this interview
  if (!jobId || (!jobDescription && !jobLoading)) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center text-sm text-gray-500">
        <AlertCircle className="w-8 h-8 mb-3 text-gray-300" />
        <p className="font-medium text-gray-700 mb-1">No job context available</p>
        <p className="text-xs">
          Interview questions are generated from the linked job&apos;s description and required
          skills.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-gray-200 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-gray-700 truncate">
            {result
              ? `${result.questions.length} questions generated`
              : "Generate interview questions"}
          </p>
          {result && (
            <p className="text-[10px] text-gray-400 mt-0.5">
              via {result.provider_used}
              {result.fallback_used ? " (fallback)" : ""}
              {" · "}
              {result.duration_ms}ms
            </p>
          )}
        </div>
        <Button
          size="sm"
          variant={result ? "outline" : "default"}
          disabled={loading || !canGenerate}
          onClick={handleGenerate}
          className="shrink-0 text-xs"
        >
          {loading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
          ) : result ? (
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          ) : null}
          {loading ? "Generating…" : result ? "Regenerate" : "Generate"}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Questions list */}
      {result && (
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {/* Category summary chips */}
          <div className="flex gap-2 flex-wrap mb-1">
            {Object.entries(result.questions_by_category).map(([cat, count]) =>
              count > 0 ? (
                <span
                  key={cat}
                  className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    CATEGORY_COLORS[cat] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {CATEGORY_LABELS[cat] ?? cat}: {count}
                </span>
              ) : null,
            )}
          </div>

          {result.questions.map((q, i) => (
            <QuestionCard key={i} question={q} index={i} />
          ))}
        </div>
      )}

      {/* Empty state — has context but not yet generated */}
      {!result && !loading && (
        <div className="flex flex-col items-center justify-center flex-1 p-6 text-center">
          <p className="text-sm text-gray-500 mb-4">
            Click <strong>Generate</strong> to create tailored interview questions based on the
            job description and required skills.
          </p>
          {requiredSkills.length > 0 && (
            <div className="flex flex-wrap gap-1 justify-center">
              {requiredSkills.slice(0, 6).map((skill, i) => (
                <span
                  key={i}
                  className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full"
                >
                  {skill}
                </span>
              ))}
              {requiredSkills.length > 6 && (
                <span className="text-[10px] text-gray-400">+{requiredSkills.length - 6} more</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 p-6">
          <Loader2 className="w-6 h-6 animate-spin text-[#FF5A1F]" />
          <p className="text-xs text-gray-500">Generating questions…</p>
        </div>
      )}
    </div>
  );
}
