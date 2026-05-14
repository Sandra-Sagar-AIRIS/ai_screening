"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Brain,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
  User,
  Briefcase,
  BarChart2,
  MessageSquare,
  RefreshCw,
  Send,
  ThumbsUp,
  ThumbsDown,
  Pause,
  Eye,
  XCircle,
  Sparkles,
  Star,
  Target,
  Clock,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getScreeningDetail,
  triggerEvaluation,
  upsertAnswer,
  recordDecision,
  regenerateQuestions,
  movePipelineStage,
} from "@/lib/api/ai_screening";
import { getPipelines } from "@/lib/api/pipeline";
import type {
  AIScreeningDetail,
  AIScreeningQuestion,
  AIScreeningAnswer,
  AIScreeningEvaluation,
  Pipeline,
  ScreeningStatus,
  ScreeningRecommendation,
  RecruiterDecision,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

// ── Helpers ───────────────────────────────────────────────────────────────────

const TRANSIENT_STATUSES = new Set(["pending", "generating_questions", "evaluating"]);

function statusColor(status: ScreeningStatus) {
  return {
    pending: "bg-gray-100 text-gray-600",
    generating_questions: "bg-blue-100 text-blue-700",
    questions_ready: "bg-yellow-100 text-yellow-700",
    evaluating: "bg-purple-100 text-purple-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    cancelled: "bg-gray-100 text-gray-500",
  }[status] ?? "bg-gray-100 text-gray-600";
}

function statusLabel(status: ScreeningStatus) {
  return {
    pending: "Pending",
    generating_questions: "Generating Questions…",
    questions_ready: "Questions Ready",
    evaluating: "AI Evaluating…",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
  }[status] ?? status;
}

function recLabel(rec: ScreeningRecommendation | null) {
  if (!rec) return null;
  return {
    strong_proceed: "Strong Proceed",
    proceed: "Proceed",
    needs_manual_review: "Manual Review",
    weak_match: "Weak Match",
    reject_recommendation: "Reject",
  }[rec];
}

function recColor(rec: ScreeningRecommendation | null) {
  if (!rec) return "";
  return {
    strong_proceed: "bg-emerald-100 text-emerald-800 border-emerald-200",
    proceed: "bg-green-100 text-green-700 border-green-200",
    needs_manual_review: "bg-yellow-100 text-yellow-700 border-yellow-200",
    weak_match: "bg-orange-100 text-orange-700 border-orange-200",
    reject_recommendation: "bg-red-100 text-red-700 border-red-200",
  }[rec] ?? "";
}

function ScoreCircle({ score, label }: { score: number | null; label: string }) {
  if (score === null) {
    return (
      <div className="flex flex-col items-center">
        <div className="w-16 h-16 rounded-full border-4 border-gray-200 flex items-center justify-center">
          <span className="text-gray-400 text-xs">—</span>
        </div>
        <span className="text-xs text-gray-500 mt-1">{label}</span>
      </div>
    );
  }
  const pct = Math.min(100, Math.max(0, score));
  const strokeColor =
    pct >= 75 ? "#10b981" : pct >= 55 ? "#f59e0b" : "#ef4444";
  const r = 26;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ - (circ * pct) / 100;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-16 h-16">
        <svg width="64" height="64" className="-rotate-90">
          <circle cx="32" cy="32" r={r} fill="none" stroke="#e5e7eb" strokeWidth="6" />
          <circle
            cx="32" cy="32" r={r} fill="none"
            stroke={strokeColor} strokeWidth="6"
            strokeDasharray={circ}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-gray-800">
          {Math.round(pct)}
        </span>
      </div>
      <span className="text-xs text-gray-500 mt-1 text-center">{label}</span>
    </div>
  );
}

// ── Question card ─────────────────────────────────────────────────────────────

function QuestionCard({
  question,
  answer,
  evaluation,
  isComplete,
  onAnswerSave,
}: {
  question: AIScreeningQuestion;
  answer: AIScreeningAnswer | undefined;
  evaluation: AIScreeningEvaluation | undefined;
  isComplete: boolean;
  onAnswerSave: (questionId: string, text: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [answerText, setAnswerText] = useState(answer?.answer_text ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const difficultyColor = {
    easy: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    hard: "bg-red-100 text-red-700",
  }[question.difficulty] ?? "bg-gray-100 text-gray-600";

  const categoryLabel = question.category.replace("_", " ");

  const handleTextChange = (text: string) => {
    setAnswerText(text);
    setSaved(false);
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    autoSaveRef.current = setTimeout(async () => {
      if (text.trim()) {
        setSaving(true);
        await onAnswerSave(question.id, text);
        setSaving(false);
        setSaved(true);
      }
    }, 1500);
  };

  const handleManualSave = async () => {
    if (!answerText.trim()) return;
    setSaving(true);
    await onAnswerSave(question.id, answerText);
    setSaving(false);
    setSaved(true);
  };

  const hasAnswer = Boolean(answer?.answer_text || answerText.trim());
  const scoreColor =
    evaluation?.ai_score !== null && evaluation?.ai_score !== undefined
      ? evaluation.ai_score >= 7 ? "text-green-600" : evaluation.ai_score >= 5 ? "text-yellow-600" : "text-red-600"
      : "text-gray-400";

  return (
    <Card className="border border-gray-200 shadow-none">
      <div
        className="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 rounded-lg transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        {/* Question number */}
        <div className="w-7 h-7 rounded-full bg-orange-100 flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-xs font-bold text-orange-600">{question.position}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium capitalize", difficultyColor)}>
              {question.difficulty}
            </span>
            <span className="text-xs text-gray-500 capitalize">{categoryLabel}</span>
            {hasAnswer && <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
          </div>
          <p className="text-sm text-gray-800 font-medium leading-snug">{question.question_text}</p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {evaluation?.ai_score !== undefined && evaluation?.ai_score !== null && (
            <span className={cn("text-lg font-bold", scoreColor)}>
              {evaluation.ai_score}/10
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3 space-y-4">
          {/* Answer input */}
          {!isComplete && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-gray-600">
                Candidate Answer
                <span className="text-gray-400 font-normal ml-1">(enter the candidate's response)</span>
              </label>
              <textarea
                value={answerText}
                onChange={(e) => handleTextChange(e.target.value)}
                placeholder="Type the candidate's response here…"
                rows={4}
                className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm resize-none outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-200 transition-colors"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">
                  {saving ? "Saving…" : saved ? "✓ Saved" : "Auto-saves after typing"}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1.5 text-xs"
                  onClick={handleManualSave}
                  disabled={saving || !answerText.trim()}
                >
                  <Send className="w-3 h-3" />
                  Save Answer
                </Button>
              </div>
            </div>
          )}

          {/* Saved answer (read-only when complete) */}
          {isComplete && answer?.answer_text && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-600">Candidate Answer</p>
              <div className="bg-gray-50 rounded-md p-3 text-sm text-gray-700 whitespace-pre-wrap">
                {answer.answer_text}
              </div>
            </div>
          )}

          {/* AI evaluation */}
          {evaluation && (
            <div className="space-y-3 pt-2 border-t border-gray-100">
              <div className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-orange-500" />
                <span className="text-xs font-semibold text-gray-700">AI Evaluation</span>
                {evaluation.confidence !== null && (
                  <span className="text-xs text-gray-400">
                    (Confidence: {evaluation.confidence}%)
                  </span>
                )}
              </div>

              {/* Scores row */}
              <div className="flex items-center gap-4">
                {[
                  { label: "Overall", value: evaluation.ai_score },
                  { label: "Communication", value: evaluation.communication_rating },
                  { label: "Technical", value: evaluation.technical_rating },
                ].map(({ label, value }) => (
                  <div key={label} className="text-center">
                    <span
                      className={cn(
                        "text-xl font-bold",
                        value !== null
                          ? value >= 7 ? "text-green-600" : value >= 5 ? "text-yellow-600" : "text-red-600"
                          : "text-gray-300"
                      )}
                    >
                      {value ?? "—"}
                    </span>
                    <p className="text-xs text-gray-500">{label}</p>
                  </div>
                ))}
              </div>

              {evaluation.reasoning && (
                <p className="text-sm text-gray-700 leading-relaxed">{evaluation.reasoning}</p>
              )}

              <div className="grid grid-cols-2 gap-3">
                {evaluation.strengths && evaluation.strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-green-700 mb-1 flex items-center gap-1">
                      <ThumbsUp className="w-3 h-3" /> Strengths
                    </p>
                    <ul className="space-y-0.5">
                      {evaluation.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-gray-600">• {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {evaluation.concerns && evaluation.concerns.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-red-600 mb-1 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> Concerns
                    </p>
                    <ul className="space-y-0.5">
                      {evaluation.concerns.map((c, i) => (
                        <li key={i} className="text-xs text-gray-600">• {c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {evaluation.follow_up_suggestion && (
                <div className="bg-blue-50 rounded-md p-2.5">
                  <p className="text-xs font-medium text-blue-700 mb-1">Follow-up for Human Interview</p>
                  <p className="text-xs text-blue-600">{evaluation.follow_up_suggestion}</p>
                </div>
              )}
            </div>
          )}

          {/* Expected signals (guidance for recruiter) */}
          {question.expected_signals && !evaluation && (
            <div className="bg-amber-50 rounded-md p-3">
              <p className="text-xs font-medium text-amber-700 mb-1.5 flex items-center gap-1">
                <Target className="w-3 h-3" /> What to listen for
              </p>
              {question.expected_signals.key_concepts && (
                <p className="text-xs text-amber-700">
                  <span className="font-medium">Key concepts: </span>
                  {question.expected_signals.key_concepts.join(", ")}
                </p>
              )}
              {question.expected_signals.ideal_depth && (
                <p className="text-xs text-amber-600 mt-1">{question.expected_signals.ideal_depth}</p>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Decision panel ────────────────────────────────────────────────────────────

function DecisionPanel({
  currentDecision,
  currentNotes,
  onDecision,
}: {
  currentDecision: string | null;
  currentNotes: string | null;
  onDecision: (decision: RecruiterDecision, notes: string) => Promise<void>;
}) {
  const [notes, setNotes] = useState(currentNotes ?? "");
  const [saving, setSaving] = useState(false);

  const DECISIONS: { value: RecruiterDecision; label: string; icon: React.ElementType; color: string }[] = [
    { value: "advance", label: "Advance to Interviews", icon: ThumbsUp, color: "bg-green-600 hover:bg-green-700 text-white" },
    { value: "hold", label: "Hold for Review", icon: Pause, color: "bg-yellow-500 hover:bg-yellow-600 text-white" },
    { value: "needs_review", label: "Needs More Review", icon: Eye, color: "bg-blue-500 hover:bg-blue-600 text-white" },
    { value: "reject", label: "Reject", icon: XCircle, color: "bg-red-500 hover:bg-red-600 text-white" },
  ];

  const handle = async (decision: RecruiterDecision) => {
    setSaving(true);
    await onDecision(decision, notes);
    setSaving(false);
  };

  return (
    <div className="space-y-4">
      {currentDecision && (
        <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-xs font-medium text-gray-600">Current Decision</p>
          <p className="text-sm font-semibold text-gray-800 capitalize mt-0.5">{currentDecision}</p>
          {currentNotes && <p className="text-xs text-gray-500 mt-1">{currentNotes}</p>}
        </div>
      )}

      <div>
        <label className="text-xs font-medium text-gray-600 block mb-1.5">
          Recruiter Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add notes about this decision…"
          rows={3}
          className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm resize-none outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-200 transition-colors"
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        {DECISIONS.map(({ value, label, icon: Icon, color }) => (
          <Button
            key={value}
            className={cn("gap-2 text-xs h-9", color)}
            onClick={() => handle(value)}
            disabled={saving}
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
            {label}
          </Button>
        ))}
      </div>

      <p className="text-xs text-gray-400 text-center">
        AI recommendations are advisory. You make the final decision.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ScreeningDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [screening, setScreening] = useState<AIScreeningDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [movingStage, setMovingStage] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getScreeningDetail(id);
      setScreening(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load screening");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Load associated pipeline so we can offer stage-move actions
  useEffect(() => {
    if (!screening?.candidate_id || !screening?.job_id) return;
    const cid = String(screening.candidate_id);
    const jid = String(screening.job_id);
    getPipelines(1, 0, jid, cid)
      .then((rows) => { if (rows.length > 0) setPipeline(rows[0]); })
      .catch(() => {});
  }, [screening?.candidate_id, screening?.job_id]);

  // Auto-poll when in transient status
  useEffect(() => {
    if (!screening || !TRANSIENT_STATUSES.has(screening.status)) return;
    const interval = setInterval(load, 2500);
    return () => clearInterval(interval);
  }, [screening, load]);

  const handleEvaluate = async () => {
    if (!screening) return;
    setActionLoading(true);
    try {
      const updated = await triggerEvaluation(screening.id);
      setScreening((prev) => prev ? { ...prev, ...updated } : prev);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!screening) return;
    setActionLoading(true);
    try {
      const updated = await regenerateQuestions(screening.id);
      setScreening((prev) => prev ? { ...prev, ...updated, questions: [] } : prev);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAnswerSave = async (questionId: string, text: string) => {
    if (!screening) return;
    try {
      const answer = await upsertAnswer(screening.id, questionId, { answer_text: text });
      setScreening((prev) => {
        if (!prev) return prev;
        const existing = prev.answers.find((a) => a.question_id === questionId);
        return {
          ...prev,
          answers: existing
            ? prev.answers.map((a) => a.question_id === questionId ? answer : a)
            : [...prev.answers, answer],
        };
      });
    } catch (e) {
      console.error("Failed to save answer", e);
    }
  };

  const handleDecision = async (decision: RecruiterDecision, notes: string) => {
    if (!screening) return;
    const updated = await recordDecision(screening.id, { decision, notes: notes || null });
    setScreening((prev) => prev ? { ...prev, ...updated } : prev);
  };

  const handleMoveStage = async (stage: string) => {
    if (!screening || !pipeline) return;
    setMovingStage(true);
    try {
      await movePipelineStage(screening.id, pipeline.id, stage);
      setPipeline((prev) => prev ? { ...prev, stage: stage as Pipeline["stage"] } : prev);
    } catch (e) {
      console.error("Failed to move stage", e);
    } finally {
      setMovingStage(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
      </div>
    );
  }

  if (error || !screening) {
    return (
      <div className="p-6">
        <p className="text-red-600">{error ?? "Screening not found"}</p>
        <Button variant="link" onClick={() => router.push("/ai-screenings")}>← Back</Button>
      </div>
    );
  }

  const isComplete = screening.status === "completed";
  const isTransient = TRANSIENT_STATUSES.has(screening.status);
  const canEvaluate = screening.status === "questions_ready" &&
    screening.answers.length > 0;
  const answeredCount = screening.answers.length;
  const totalQuestions = screening.questions.length;

  // Build lookup maps
  const answersByQid = Object.fromEntries(screening.answers.map((a) => [a.question_id, a]));
  const evalByQid = Object.fromEntries(screening.evaluations.map((e) => [e.question_id, e]));

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/ai-screenings">
              <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-gray-600">
                <ArrowLeft className="w-4 h-4" />
                All Screenings
              </Button>
            </Link>
            <div className="w-px h-5 bg-gray-200" />
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-orange-500" />
              <span className="font-semibold text-gray-900">
                AI Screening — {screening.candidate_name ?? "Candidate"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium", statusColor(screening.status))}>
              {isTransient && <Loader2 className="w-3 h-3 animate-spin inline mr-1" />}
              {statusLabel(screening.status)}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={load}
              className="h-8 gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* ── LEFT: Main content ── */}
          <div className="xl:col-span-2 space-y-5">

            {/* Context card */}
            <Card className="border border-gray-200 shadow-none">
              <CardContent className="pt-4 pb-3">
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-400" />
                    <span className="font-medium text-gray-900">{screening.candidate_name}</span>
                    {screening.candidate_email && (
                      <span className="text-gray-500">{screening.candidate_email}</span>
                    )}
                  </div>
                  {screening.job_title && (
                    <div className="flex items-center gap-2">
                      <Briefcase className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-700">{screening.job_title}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-500">
                      {new Date(screening.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {screening.ats_score !== null && (
                    <div className="flex items-center gap-2 ml-auto">
                      <TrendingUp className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-600">
                        ATS Score: <span className="font-semibold">{Math.round(screening.ats_score)}</span>
                      </span>
                      {screening.ats_recommendation && (
                        <span className="text-xs text-gray-500 capitalize">
                          ({screening.ats_recommendation.replace("_", " ")})
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Status banner for transient states */}
            {isTransient && (
              <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin shrink-0" />
                <div>
                  <p className="font-medium text-blue-800 text-sm">
                    {screening.status === "generating_questions" && "AI is generating screening questions…"}
                    {screening.status === "pending" && "Preparing your screening session…"}
                    {screening.status === "evaluating" && "AI is evaluating candidate answers…"}
                  </p>
                  <p className="text-blue-600 text-xs mt-0.5">
                    This page updates automatically. You can leave and come back.
                  </p>
                </div>
              </div>
            )}

            {/* Failed state */}
            {screening.status === "failed" && (
              <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                <XCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-red-800 text-sm">AI processing failed</p>
                  <p className="text-red-600 text-xs mt-1">
                    You can retry question generation or proceed with manual review.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-300 text-red-600 hover:bg-red-50 shrink-0"
                  onClick={handleRegenerate}
                  disabled={actionLoading}
                >
                  {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  Retry
                </Button>
              </div>
            )}

            {/* Progress indicator */}
            {screening.status === "questions_ready" && totalQuestions > 0 && (
              <div className="flex items-center justify-between p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-yellow-600" />
                  <span className="text-sm text-yellow-800">
                    <span className="font-semibold">{answeredCount}/{totalQuestions}</span> answers entered
                  </span>
                </div>
                {canEvaluate && (
                  <Button
                    size="sm"
                    className="bg-orange-600 hover:bg-orange-700 text-white gap-1.5 h-8"
                    onClick={handleEvaluate}
                    disabled={actionLoading}
                  >
                    {actionLoading
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <Sparkles className="w-3.5 h-3.5" />}
                    Run AI Evaluation
                  </Button>
                )}
              </div>
            )}

            {/* AI Summary */}
            {isComplete && screening.ai_summary && (
              <Card className="border border-orange-200 bg-orange-50 shadow-none">
                <CardHeader className="pb-2 pt-4">
                  <CardTitle className="text-sm flex items-center gap-2 text-orange-800">
                    <Sparkles className="w-4 h-4" />
                    AI Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-4">
                  <p className="text-sm text-orange-900 whitespace-pre-wrap leading-relaxed">
                    {screening.ai_summary}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Questions */}
            {totalQuestions > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-gray-500" />
                    Screening Questions ({totalQuestions})
                  </h2>
                  {!isComplete && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 gap-1.5 text-xs"
                      onClick={handleRegenerate}
                      disabled={actionLoading || isTransient}
                    >
                      <RefreshCw className="w-3 h-3" />
                      Regenerate
                    </Button>
                  )}
                </div>

                {screening.questions.map((q) => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    answer={answersByQid[q.id]}
                    evaluation={evalByQid[q.id]}
                    isComplete={isComplete}
                    onAnswerSave={handleAnswerSave}
                  />
                ))}
              </div>
            )}

            {/* Empty state for questions */}
            {totalQuestions === 0 && !isTransient && (
              <div className="text-center py-10 text-gray-400">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No questions generated yet.</p>
              </div>
            )}
          </div>

          {/* ── RIGHT: Scores + Decision ── */}
          <div className="space-y-5">

            {/* Scores */}
            {isComplete && (
              <Card className="border border-gray-200 shadow-none">
                <CardHeader className="pb-2 pt-4">
                  <CardTitle className="text-sm flex items-center gap-2 text-gray-700">
                    <BarChart2 className="w-4 h-4" />
                    AI Scores
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-4">
                  <div className="flex items-center justify-around py-2">
                    <ScoreCircle score={screening.overall_score} label="Overall" />
                    <ScoreCircle score={screening.technical_score} label="Technical" />
                    <ScoreCircle score={screening.communication_score} label="Communication" />
                  </div>
                  {screening.confidence_score !== null && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                        <span>AI Confidence</span>
                        <span className="font-medium">{Math.round(screening.confidence_score ?? 0)}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-400 rounded-full"
                          style={{ width: `${screening.confidence_score ?? 0}%` }}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* AI Recommendation */}
            {screening.recommendation && (
              <Card className={cn("border shadow-none", recColor(screening.recommendation))}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Star className="w-4 h-4" />
                    <span className="text-xs font-semibold uppercase tracking-wide">AI Recommendation</span>
                  </div>
                  <p className="text-lg font-bold">{recLabel(screening.recommendation)}</p>
                  <p className="text-xs mt-1 opacity-75">
                    This is advisory. The final decision is yours.
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Recruiter Decision */}
            <Card className="border border-gray-200 shadow-none">
              <CardHeader className="pb-2 pt-4">
                <CardTitle className="text-sm flex items-center gap-2 text-gray-700">
                  <User className="w-4 h-4" />
                  Recruiter Decision
                </CardTitle>
              </CardHeader>
              <CardContent className="pb-4">
                <DecisionPanel
                  currentDecision={screening.recruiter_decision}
                  currentNotes={screening.recruiter_notes}
                  onDecision={handleDecision}
                />
              </CardContent>
            </Card>

            {/* Pipeline Stage Move */}
            {pipeline && (
              <Card className="border border-gray-200 shadow-none">
                <CardHeader className="pb-2 pt-4">
                  <CardTitle className="text-sm flex items-center gap-2 text-gray-700">
                    <TrendingUp className="w-4 h-4" />
                    Pipeline Stage
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-4 space-y-2">
                  <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg border border-slate-100 mb-2">
                    <span className="text-xs text-slate-500">Current stage</span>
                    <span className="text-xs font-bold text-slate-700 capitalize">
                      {pipeline.stage.replace("_", " ")}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { stage: "screening", label: "Screening", color: "border-sky-200 text-sky-700 hover:bg-sky-50" },
                      { stage: "interview", label: "→ Interview", color: "border-emerald-200 text-emerald-700 hover:bg-emerald-50" },
                      { stage: "offer", label: "→ Offer", color: "border-amber-200 text-amber-700 hover:bg-amber-50" },
                      { stage: "rejected", label: "Reject", color: "border-red-200 text-red-600 hover:bg-red-50" },
                    ].map(({ stage, label, color }) => (
                      <Button
                        key={stage}
                        variant="outline"
                        size="sm"
                        className={`h-8 text-xs font-medium ${color} ${pipeline.stage === stage ? "opacity-40 cursor-not-allowed" : ""}`}
                        disabled={movingStage || pipeline.stage === stage}
                        onClick={() => handleMoveStage(stage)}
                      >
                        {movingStage ? <Loader2 className="w-3 h-3 animate-spin" /> : label}
                      </Button>
                    ))}
                  </div>
                  <p className="text-[11px] text-gray-400 text-center pt-1">
                    Move candidate through the pipeline
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Token usage (debug info) */}
            {(screening.prompt_tokens_used || screening.completion_tokens_used) ? (
              <div className="text-xs text-gray-400 p-3 bg-gray-50 rounded-lg">
                <p className="font-medium text-gray-500 mb-1">AI Usage</p>
                <p>Prompt tokens: {(screening.prompt_tokens_used ?? 0).toLocaleString()}</p>
                <p>Completion tokens: {(screening.completion_tokens_used ?? 0).toLocaleString()}</p>
                {screening.ai_model && <p>Model: {screening.ai_model}</p>}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
