"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { submitFeedback } from "@/lib/api/interviews";
import type { FeedbackRecommendation } from "@/lib/api/types";

const RECOMMENDATIONS: { value: FeedbackRecommendation; label: string }[] = [
  { value: "strong_yes", label: "Strong Yes" },
  { value: "yes",        label: "Yes" },
  { value: "neutral",    label: "Neutral" },
  { value: "no",         label: "No" },
  { value: "strong_no",  label: "Strong No" },
];

const SCORE_CATEGORIES: { key: keyof ScoreState; label: string }[] = [
  { key: "technical_score",        label: "Technical" },
  { key: "communication_score",    label: "Communication" },
  { key: "problem_solving_score",  label: "Problem Solving" },
  { key: "culture_fit_score",      label: "Culture Fit" },
  { key: "system_design_score",    label: "System Design" },
  { key: "leadership_score",       label: "Leadership" },
];

interface ScoreState {
  technical_score: number | null;
  communication_score: number | null;
  problem_solving_score: number | null;
  culture_fit_score: number | null;
  system_design_score: number | null;
  leadership_score: number | null;
}

interface Props {
  interviewId: string;
  onSubmit?: () => void;
}

function ScoreSelector({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-xs text-gray-500">{label}</label>
        {value !== null && (
          <span className="text-[10px] text-[#FF5A1F] font-semibold">{value}/5</span>
        )}
      </div>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(value === n ? null : n)}
            className={`h-7 w-7 rounded-md border text-xs font-semibold transition-colors ${
              value !== null && n <= value
                ? "border-[#FF5A1F] bg-[#FF5A1F] text-white"
                : "border-gray-200 bg-white text-gray-600 hover:border-[#FF5A1F] hover:text-[#FF5A1F]"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export function InterviewFeedbackForm({ interviewId, onSubmit }: Props) {
  const [scores, setScores] = useState<ScoreState>({
    technical_score: null,
    communication_score: null,
    problem_solving_score: null,
    culture_fit_score: null,
    system_design_score: null,
    leadership_score: null,
  });
  const [rating, setRating] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState<FeedbackRecommendation | "">("");
  const [strengths, setStrengths] = useState("");
  const [weaknesses, setWeaknesses] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const setScore = (key: keyof ScoreState, val: number | null) =>
    setScores((prev) => ({ ...prev, [key]: val }));

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback(interviewId, {
        ...scores,
        rating: rating ?? undefined,
        recommendation: recommendation || undefined,
        strengths: strengths.trim() || undefined,
        weaknesses: weaknesses.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      setDone(true);
      onSubmit?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <p className="text-xs text-green-700 font-medium py-2">
        Feedback submitted successfully.
      </p>
    );
  }

  const hasAnyInput =
    Object.values(scores).some((v) => v !== null) ||
    rating !== null ||
    !!recommendation ||
    !!notes.trim();

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Add Feedback</p>

      {/* Structured scores */}
      <div className="rounded-lg border border-gray-100 bg-white p-3 space-y-3">
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Scores</p>
        {SCORE_CATEGORIES.map(({ key, label }) => (
          <ScoreSelector
            key={key}
            label={label}
            value={scores[key]}
            onChange={(v) => setScore(key, v)}
          />
        ))}
      </div>

      {/* Overall rating */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500">Overall Rating (1–5)</label>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRating(rating === n ? null : n)}
              className={`h-7 w-7 rounded-md border text-xs font-semibold transition-colors ${
                rating === n
                  ? "border-[#FF5A1F] bg-[#FF5A1F] text-white"
                  : "border-gray-200 bg-white text-gray-600 hover:border-[#FF5A1F] hover:text-[#FF5A1F]"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Recommendation */}
      <div className="space-y-1">
        <label className="text-xs text-gray-500">Recommendation</label>
        <select
          className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] bg-white"
          value={recommendation}
          onChange={(e) => setRecommendation(e.target.value as FeedbackRecommendation | "")}
        >
          <option value="">Select...</option>
          {RECOMMENDATIONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Strengths</label>
        <textarea
          rows={2}
          className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] resize-none"
          placeholder="What went well..."
          value={strengths}
          onChange={(e) => setStrengths(e.target.value)}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Areas to improve</label>
        <textarea
          rows={2}
          className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] resize-none"
          placeholder="Areas of concern..."
          value={weaknesses}
          onChange={(e) => setWeaknesses(e.target.value)}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Additional notes</label>
        <textarea
          rows={2}
          className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] resize-none"
          placeholder="Any other notes..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <Button
        size="sm"
        className="w-full h-8 text-xs bg-[#FF5A1F] hover:bg-[#E54E1A] text-white"
        onClick={handleSubmit}
        disabled={submitting || !hasAnyInput}
      >
        {submitting ? "Submitting…" : "Submit Feedback"}
      </Button>
    </div>
  );
}
