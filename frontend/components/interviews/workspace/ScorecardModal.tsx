"use client";

import { useState } from "react";
import { X, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { submitFeedback } from "@/lib/api/interviews";
import { ApiError } from "@/lib/api/client";
import type { FeedbackRecommendation, InterviewFeedback, InterviewFeedbackPayload } from "@/lib/api/types";

const SCORE_DIMENSIONS: { key: keyof InterviewFeedbackPayload; label: string; description: string }[] = [
  { key: "technical_score", label: "Technical Skills", description: "Domain knowledge, coding, problem-solving depth" },
  { key: "communication_score", label: "Communication", description: "Clarity, listening, articulating ideas" },
  { key: "problem_solving_score", label: "Problem Solving", description: "Approach, reasoning, creativity" },
  { key: "system_design_score", label: "System Design", description: "Architecture thinking, trade-offs, scalability" },
  { key: "culture_fit_score", label: "Culture Fit", description: "Values alignment, collaboration, growth mindset" },
  { key: "leadership_score", label: "Leadership", description: "Initiative, influence, ownership mentality" },
];

const RECOMMENDATIONS: { value: FeedbackRecommendation; label: string; color: string }[] = [
  { value: "strong_yes", label: "Strong Yes", color: "bg-green-600 text-white border-green-600" },
  { value: "yes", label: "Yes", color: "bg-green-100 text-green-700 border-green-300" },
  { value: "neutral", label: "Neutral", color: "bg-gray-100 text-gray-600 border-gray-300" },
  { value: "no", label: "No", color: "bg-red-100 text-red-600 border-red-300" },
  { value: "strong_no", label: "Strong No", color: "bg-red-600 text-white border-red-600" },
];

function StarRating({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (v: number) => void;
}) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(star)}
          className="transition-transform hover:scale-110"
        >
          <Star
            className={`w-5 h-5 ${
              star <= (hover || value || 0)
                ? "fill-amber-400 text-amber-400"
                : "fill-none text-gray-300"
            }`}
          />
        </button>
      ))}
      {value && <span className="text-xs text-gray-500 ml-1">{value}/5</span>}
    </div>
  );
}

type ScoreState = Record<string, number | null>;

export function ScorecardModal({
  interviewId,
  onClose,
  onSubmitted,
}: {
  interviewId: string;
  onClose: () => void;
  onSubmitted: (feedback: InterviewFeedback) => void;
}) {
  const [scores, setScores] = useState<ScoreState>(() =>
    Object.fromEntries(SCORE_DIMENSIONS.map((d) => [d.key, null])),
  );
  const [overallRating, setOverallRating] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState<FeedbackRecommendation | null>(null);
  const [strengths, setStrengths] = useState("");
  const [weaknesses, setWeaknesses] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: InterviewFeedbackPayload = {
        ...Object.fromEntries(
          SCORE_DIMENSIONS.map((d) => [d.key, scores[d.key]])
        ) as Record<string, number | null>,
        rating: overallRating,
        recommendation,
        strengths: strengths.trim() || null,
        weaknesses: weaknesses.trim() || null,
        notes: notes.trim() || null,
      };
      const feedback = await submitFeedback(interviewId, payload);
      onSubmitted(feedback);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        // Already submitted — treat as success so the modal closes cleanly
        onClose();
        return;
      }
      setError(e instanceof Error ? e.message : "Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Submit Scorecard</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Score dimensions */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Dimension Scores</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              {SCORE_DIMENSIONS.map((dim) => (
                <div key={dim.key} className="space-y-1.5">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{dim.label}</p>
                    <p className="text-xs text-gray-400">{dim.description}</p>
                  </div>
                  <StarRating
                    value={scores[dim.key]}
                    onChange={(v) => setScores((prev) => ({ ...prev, [dim.key]: v }))}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Overall rating */}
          <div className="space-y-2 border-t border-gray-100 pt-4">
            <p className="text-sm font-medium text-gray-800">Overall Rating</p>
            <StarRating value={overallRating} onChange={setOverallRating} />
          </div>

          {/* Recommendation */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-800">Recommendation</p>
            <div className="flex flex-wrap gap-2">
              {RECOMMENDATIONS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRecommendation(recommendation === r.value ? null : r.value)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                    recommendation === r.value ? r.color : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Text fields */}
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Strengths</label>
              <textarea
                rows={2}
                className="w-full rounded-lg border border-gray-200 p-2.5 text-sm resize-none focus:outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F]"
                placeholder="What did the candidate do well?"
                value={strengths}
                onChange={(e) => setStrengths(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Areas for Improvement</label>
              <textarea
                rows={2}
                className="w-full rounded-lg border border-gray-200 p-2.5 text-sm resize-none focus:outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F]"
                placeholder="What could be improved?"
                value={weaknesses}
                onChange={(e) => setWeaknesses(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Additional Notes</label>
              <textarea
                rows={2}
                className="w-full rounded-lg border border-gray-200 p-2.5 text-sm resize-none focus:outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F]"
                placeholder="Any other observations…"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            className="bg-[#FF5A1F] hover:bg-[#e04e18] text-white"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? "Submitting…" : "Submit Scorecard"}
          </Button>
        </div>
      </div>
    </div>
  );
}
