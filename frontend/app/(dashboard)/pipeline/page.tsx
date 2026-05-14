"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  closestCorners,
  DndContext,
  DragOverlay,
  type DragEndEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { Brain, GripVertical, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getJobMatchesAts, rescoreJobAts } from "@/lib/api/ats";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import { listScreenings } from "@/lib/api/ai_screening";
import { PIPELINE_UPDATE_PERMISSION, hasPermission } from "@/lib/rbac";
import type { AIScreeningListItem, Candidate, Job, Pipeline } from "@/lib/api/types";
import { StartScreeningModal } from "@/components/pipeline/StartScreeningModal";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { ATSRecommendationBadge } from "@/components/ats/ats-recommendation-badge";
import { ATSScoreBadge } from "@/components/ats/ats-score-badge";
import { normalizeCandidateId } from "@/lib/ats/candidate-id";

type BoardStage = "applied" | "screening" | "ai_screening" | "interview" | "offered" | "hired";

const STAGES: BoardStage[] = ["applied", "screening", "ai_screening", "interview", "offered", "hired"];
const STAGE_LABELS: Record<BoardStage, string> = {
  applied: "Applied",
  screening: "Screening",
  ai_screening: "AI Screening",
  interview: "Interview",
  offered: "Offered",
  hired: "Hired",
};
const STAGE_ACCENT: Record<BoardStage, string> = {
  applied: "bg-violet-400",
  screening: "bg-sky-400",
  ai_screening: "bg-orange-400",
  interview: "bg-emerald-400",
  offered: "bg-amber-400",
  hired: "bg-cyan-400",
};

function toBoardStage(stage: Pipeline["stage"]): BoardStage {
  if (stage === "offer") return "offered";
  if (stage === "placed") return "hired";
  if ((stage as string) === "ai_screening") return "ai_screening";
  return stage as BoardStage;
}

function toPipelineStage(stage: BoardStage): Pipeline["stage"] {
  if (stage === "offered") return "offer";
  if (stage === "hired") return "placed";
  if (stage === "ai_screening") return "ai_screening" as Pipeline["stage"];
  return stage;
}

// ── AI screening status badge helpers ─────────────────────────────────────────

const SCREENING_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  generating_questions: "Generating…",
  questions_ready: "Ready",
  evaluating: "Evaluating…",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const SCREENING_STATUS_COLORS: Record<string, string> = {
  pending: "bg-slate-100 text-slate-500",
  generating_questions: "bg-orange-50 text-orange-500",
  questions_ready: "bg-sky-50 text-sky-600",
  evaluating: "bg-orange-50 text-orange-500",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-600",
  cancelled: "bg-slate-100 text-slate-400",
};

function AIScreeningBadge({ screening }: { screening: AIScreeningListItem }) {
  const label = SCREENING_STATUS_LABELS[screening.status] ?? screening.status;
  const color = SCREENING_STATUS_COLORS[screening.status] ?? "bg-slate-100 text-slate-500";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${color}`}>
      <Brain className="h-2.5 w-2.5" />
      {label}
      {screening.overall_score !== null && screening.overall_score !== undefined && (
        <span className="ml-0.5 opacity-70">{Math.round(screening.overall_score)}%</span>
      )}
    </span>
  );
}

function CandidateCard({
  pipeline,
  candidate,
  atsScore,
  recommendation,
  semanticInsight,
  aiEnrichmentStatus,
  awaitingAtsMatch,
  boardLoading,
  isMoving,
  isTopMatch,
  isDragging,
}: {
  pipeline: Pipeline;
  candidate?: Candidate;
  atsScore?: number;
  recommendation?: string;
  semanticInsight?: string | null;
  aiEnrichmentStatus?: string | null;
  awaitingAtsMatch?: boolean;
  boardLoading?: boolean;
  isMoving?: boolean;
  isTopMatch?: boolean;
  isDragging?: boolean;
}) {
  const isAiStage = (pipeline.stage as string) === "ai_screening";
  return (
    <div 
      className={`relative group transition-all duration-300 w-full cursor-grab active:cursor-grabbing 
        ${isMoving ? 'opacity-70' : ''} 
        ${isDragging ? 'z-50' : 'hover:-translate-y-1'}`}
    >
      <div className={`relative rounded-[20px] bg-white p-5 border transition-all duration-300 h-full
        ${isDragging 
          ? 'shadow-[0_20px_50px_rgba(0,0,0,0.15)] border-orange-200 scale-[1.02]' 
          : 'border-slate-100/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)] hover:shadow-[0_8px_24px_rgba(0,0,0,0.06)] hover:border-slate-200'
        }`}
      >
        {/* Drag Handle Cue */}
        <div className="absolute right-4 top-5 opacity-0 group-hover:opacity-30 transition-opacity">
          <GripVertical className="h-4 w-4 text-slate-400" />
        </div>

        <Link href={`/candidates/${pipeline.candidate_id}`} className="block">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-50 border border-slate-100/80 text-[11px] font-bold text-slate-600 transition-colors duration-300 group-hover:bg-orange-50 group-hover:text-[#FF5A1F] group-hover:border-orange-100">
              {candidate ? `${candidate.first_name.charAt(0)}${candidate.last_name.charAt(0)}` : "?"}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[14px] font-bold leading-tight text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">
                {candidate ? `${candidate.first_name} ${candidate.last_name}` : "Unknown candidate"}
              </p>
              <p className="truncate text-[12px] text-slate-500 font-medium mt-0.5">{candidate?.role ?? "Role not specified"}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3 mb-4">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Exp</span>
              <span className="text-[12px] text-slate-700 font-bold">
                {candidate?.years_experience !== null && candidate?.years_experience !== undefined ? `${candidate.years_experience}y` : "-"}
              </span>
            </div>
            {isTopMatch && (
              <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[9px] font-bold text-emerald-600 border border-emerald-100 uppercase tracking-wider">
                Top Match
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <ATSScoreBadge
              score={atsScore}
              scorePending={Boolean(awaitingAtsMatch && !boardLoading)}
              compact
            />
            <ATSRecommendationBadge recommendation={recommendation} awaitingMatch={awaitingAtsMatch && !boardLoading} compact />
          </div>

          {semanticInsight ? (
            <div className="mt-4 p-3 rounded-xl bg-violet-50/40 border border-violet-100/30">
              <p className="line-clamp-2 text-[11px] leading-relaxed text-violet-600/90 italic" title={semanticInsight}>
                "{semanticInsight}"
              </p>
            </div>
          ) : aiEnrichmentStatus === "failed" ? (
            <p className="mt-4 text-[11px] leading-snug text-slate-400">
              AI insights currently unavailable.
            </p>
          ) : null}
        </Link>
        {isMoving ? (
          <div className="mt-4 pt-4 border-t border-slate-50 flex items-center gap-2">
            <RefreshCw className="h-3 w-3 text-[#FF5A1F] animate-spin" />
            <p className="text-[10px] font-bold text-[#FF5A1F] uppercase tracking-wider">Syncing stage...</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DraggableCandidateCard({
  pipeline,
  candidate,
  atsScore,
  recommendation,
  semanticInsight,
  aiEnrichmentStatus,
  awaitingAtsMatch,
  boardLoading,
  canDrag,
  isMoving,
  isTopMatch,
  aiScreening,
  onStartScreening,
}: {
  pipeline: Pipeline;
  candidate?: Candidate;
  atsScore?: number;
  recommendation?: string;
  semanticInsight?: string | null;
  aiEnrichmentStatus?: string | null;
  awaitingAtsMatch?: boolean;
  boardLoading?: boolean;
  canDrag: boolean;
  isMoving: boolean;
  isTopMatch?: boolean;
  aiScreening?: AIScreeningListItem | null;
  onStartScreening?: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: pipeline.id,
    disabled: !canDrag,
  });

  const style = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    zIndex: isDragging ? 100 : undefined,
    touchAction: "none", // Prevent scrolling while dragging
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${isDragging ? "opacity-40" : ""}`}
      {...attributes}
      {...listeners}
    >
      <CandidateCard
        pipeline={pipeline}
        candidate={candidate}
        atsScore={atsScore}
        recommendation={recommendation}
        semanticInsight={semanticInsight}
        aiEnrichmentStatus={aiEnrichmentStatus}
        awaitingAtsMatch={awaitingAtsMatch}
        boardLoading={boardLoading}
        isMoving={isMoving}
        isTopMatch={isTopMatch}
        isDragging={isDragging}
      />
    </div>
  );
}

function StageColumn({
  stage,
  count,
  isDropEnabled,
  activePipelineId,
  children,
}: {
  stage: BoardStage;
  count: number;
  isDropEnabled: boolean;
  activePipelineId: string | null;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: stage,
    data: { stage },
  });
  const isDropTarget = isOver && Boolean(activePipelineId) && isDropEnabled;
  const isDraggingAny = Boolean(activePipelineId);

  return (
    <div className="relative group transition-all duration-300 cursor-default h-full">
      <div
        ref={setNodeRef}
        className={`relative flex flex-col h-[calc(100vh-320px)] min-h-[500px] min-w-[340px] rounded-[24px] bg-slate-50/30 border transition-all duration-300 ${isDropTarget ? "bg-orange-50/40 border-orange-200 shadow-[0_8px_30px_rgba(255,90,31,0.06)] scale-[1.005]" : "border-slate-100/60 shadow-[0_2px_12px_rgba(0,0,0,0.01)]"
          }`}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-slate-50/80 backdrop-blur-md p-5 rounded-t-[24px] border-b border-slate-100/80 mb-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${STAGE_ACCENT[stage]} shadow-[0_0_8px_rgba(0,0,0,0.1)]`} />
            <p className="truncate text-[13px] font-bold tracking-wider uppercase text-slate-600">{STAGE_LABELS[stage]}</p>
          </div>
          <span className="flex items-center justify-center h-6 min-w-6 rounded-lg bg-white px-2 text-[11px] font-bold text-slate-500 shadow-sm border border-slate-100/80">
            {count}
          </span>
        </div>
        <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-4 scrollbar-hide hover:scrollbar-default transition-all">
          {isDropTarget ? (
            <div className="rounded-2xl border-2 border-dashed border-[#FF5A1F]/30 bg-orange-50/30 py-4 text-center text-[12px] font-bold text-[#FF5A1F] animate-pulse">
              Drop here
            </div>
          ) : null}
          {!count && !isDraggingAny ? <div className="h-32 rounded-[20px] border border-dashed border-slate-200/50 bg-white/30 flex items-center justify-center">
             <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">No Candidates</span>
          </div> : null}
          {children}
        </div>
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);
  const [movingPipelineId, setMovingPipelineId] = useState<string | null>(null);
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);
  // AI Screening state
  const [screeningsByCandidateId, setScreeningsByCandidateId] = useState<Record<string, AIScreeningListItem>>({});
  const [startScreeningTarget, setStartScreeningTarget] = useState<{
    pipeline: Pipeline;
    candidate: Candidate;
  } | null>(null);
  const [atsByCandidateId, setAtsByCandidateId] = useState<
    Record<
      string,
      {
        score: number;
        recommendation: string;
        recruiter_summary?: string | null;
        ai_enrichment_status?: string | null;
      }
    >
  >({});
  const [sortMode, setSortMode] = useState<"ats_desc" | "newest" | "updated">("ats_desc");
  const boardScrollRef = useRef<HTMLDivElement | null>(null);
  const pipelineLoadSeqRef = useRef(0);
  const rescoreRequestedJobIdsRef = useRef<Set<string>>(new Set());
  const canUpdatePipeline = hasPermission(permissions, PIPELINE_UPDATE_PERMISSION);
  const canReadCandidates = permissions.includes("candidates:read") || permissions.includes("candidates:read_own");
  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 10,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 200,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor)
  );

  useEffect(() => {
    async function fetchActiveCandidates() {
      const pageSize = 200; // backend enforces le=200 on /candidates limit
      let offset = 0;
      const all: Candidate[] = [];
      while (true) {
        const batch = await getCandidates(pageSize, offset, { status: "active" });
        all.push(...batch);
        if (batch.length < pageSize) {
          break;
        }
        offset += pageSize;
      }
      return all;
    }

    async function loadInitialData() {
      try {
        const [candidateData, jobData] = await Promise.all([
          canReadCandidates ? fetchActiveCandidates() : Promise.resolve([]),
          getJobs(200, 0),
        ]);
        setCandidates(candidateData);
        // Candidate matching / pipeline excludes paused and terminal jobs.
        setJobs(jobData.filter((job) => job.status === "open"));
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load pipeline setup data.");
        }
      }
    }
    void loadInitialData();
  }, [canReadCandidates]);

  async function loadPipelines(jobId: string) {
    const seq = ++pipelineLoadSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const [pipelineData, atsMatches] = await Promise.all([
        getPipelines(200, 0, jobId),
        getJobMatchesAts(jobId, { limit: 200, offset: 0, sort_by: "score_desc" }),
      ]);
      if (seq !== pipelineLoadSeqRef.current) return;
      console.info("[pipeline-board] fetched", { jobId, count: pipelineData.length });
      setPipelines(pipelineData);
      const nextAtsByCandidate: Record<
        string,
        {
          score: number;
          recommendation: string;
          recruiter_summary?: string | null;
          ai_enrichment_status?: string | null;
        }
      > = {};
      for (const item of atsMatches.matches) {
        const rawId = typeof item.candidate_id === "string" ? item.candidate_id : String(item.candidate_id);
        const cid = normalizeCandidateId(rawId);
        if (!cid) continue;
        const summary = item.recruiter_summary?.trim();
        nextAtsByCandidate[cid] = {
          score: item.fit_score,
          recommendation: item.recommendation?.trim() ?? "",
          recruiter_summary: summary
            ? summary.length > 160
              ? `${summary.slice(0, 157)}…`
              : summary
            : null,
          ai_enrichment_status: item.ai_enrichment_status,
        };
      }
      setAtsByCandidateId(nextAtsByCandidate);

      // Load AI screenings for this job so we can show badges on pipeline cards.
      // Non-critical: failures are swallowed so the board remains usable.
      void listScreenings({ job_id: jobId, limit: 200 }).then((screenings) => {
        const byCandidate: Record<string, AIScreeningListItem> = {};
        // Latest screening per candidate (list is sorted newest-first from backend)
        for (const s of screenings) {
          const cid = typeof s.candidate_id === "string" ? s.candidate_id : String(s.candidate_id);
          if (!byCandidate[cid]) {
            byCandidate[cid] = s;
          }
        }
        setScreeningsByCandidateId(byCandidate);
      }).catch(() => { /* non-critical */ });

      const hasUnscoredCandidates = pipelineData.some(
        (pipeline) => !nextAtsByCandidate[normalizeCandidateId(pipeline.candidate_id)]
      );
      if (pipelineData.length > 0 && hasUnscoredCandidates && !rescoreRequestedJobIdsRef.current.has(jobId)) {
        rescoreRequestedJobIdsRef.current.add(jobId);
        void rescoreJobAts(jobId).catch(() => {
          // Keep the board responsive even if rescoring endpoint is unavailable.
        });
      }
    } catch (err) {
      if (seq !== pipelineLoadSeqRef.current) return;
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load pipeline board.");
      }
    } finally {
      if (seq === pipelineLoadSeqRef.current) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    if (!selectedJobId) {
      return;
    }
    const interval = window.setInterval(() => {
      void loadPipelines(selectedJobId);
    }, 25000);
    return () => window.clearInterval(interval);
  }, [selectedJobId]);

  const grouped = useMemo(() => {
    const candidateMap = new Map(
      candidates.map((candidate) => [normalizeCandidateId(candidate.id), candidate])
    );
    return STAGES.reduce<Record<BoardStage, Array<{ pipeline: Pipeline; candidate: Candidate | undefined }>>>((acc, stage) => {
      acc[stage] = pipelines
        .filter((pipeline) => toBoardStage(pipeline.stage) === stage)
        .map((pipeline) => ({ pipeline, candidate: candidateMap.get(normalizeCandidateId(pipeline.candidate_id)) }))
        // Hide orphan pipeline cards so "Unknown candidate" rows don't pollute the board.
        .filter((item) => Boolean(item.candidate))
        .sort((a, b) => {
          if (sortMode === "newest") {
            return new Date(b.pipeline.created_at).getTime() - new Date(a.pipeline.created_at).getTime();
          }
          if (sortMode === "updated") {
            return new Date(b.pipeline.updated_at).getTime() - new Date(a.pipeline.updated_at).getTime();
          }
          return (
            (atsByCandidateId[normalizeCandidateId(b.pipeline.candidate_id)]?.score ?? -1) -
            (atsByCandidateId[normalizeCandidateId(a.pipeline.candidate_id)]?.score ?? -1)
          );
        });
      return acc;
    }, {} as Record<BoardStage, Array<{ pipeline: Pipeline; candidate: Candidate | undefined }>>);
  }, [candidates, pipelines, atsByCandidateId, sortMode]);

  const pipelineById = useMemo(() => new Map(pipelines.map((pipeline) => [pipeline.id, pipeline])), [pipelines]);
  const candidateById = useMemo(
    () => new Map(candidates.map((candidate) => [normalizeCandidateId(candidate.id), candidate])),
    [candidates]
  );
  const activePipeline = activePipelineId ? pipelineById.get(activePipelineId) : undefined;



  function resolveStageFromDropId(dropId: string): BoardStage | null {
    if (STAGES.includes(dropId as BoardStage)) {
      return dropId as BoardStage;
    }
    const dropPipeline = pipelineById.get(dropId);
    return dropPipeline ? toBoardStage(dropPipeline.stage) : null;
  }

  async function moveCandidateToStage(pipelineId: string, sourceStage: BoardStage, targetStage: BoardStage) {
    if (movingPipelineId || !selectedJobId || sourceStage === targetStage) return;
    setError(null);
    setMovingPipelineId(pipelineId);
    setPipelines((prev) =>
      prev.map((pipeline) => (pipeline.id === pipelineId ? { ...pipeline, stage: toPipelineStage(targetStage) } : pipeline))
    );

    try {
      await updatePipeline(pipelineId, { stage: toPipelineStage(targetStage) });
    } catch (err) {
      setPipelines((prev) =>
        prev.map((pipeline) => (pipeline.id === pipelineId ? { ...pipeline, stage: toPipelineStage(sourceStage) } : pipeline))
      );
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to move candidate.");
      }
    } finally {
      setMovingPipelineId(null);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActivePipelineId(null);

    if (!canUpdatePipeline || movingPipelineId) return;

    const sourceId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : null;
    if (!overId) return;

    const sourcePipeline = pipelineById.get(sourceId);
    if (!sourcePipeline) return;

    const sourceStage = toBoardStage(sourcePipeline.stage);
    const targetStage = resolveStageFromDropId(overId);
    if (!targetStage || sourceStage === targetStage) return;

    await moveCandidateToStage(sourceId, sourceStage, targetStage);
  }

  return (
    <section className="min-w-0 space-y-6 pb-12">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Pipeline Board</h1>
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div className="w-full max-w-sm">
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">Select Job</label>
            <select
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm outline-none transition focus:border-slate-300 focus:ring-2 focus:ring-slate-200"
              value={selectedJobId}
              onChange={(event) => {
                const nextJobId = event.target.value;
                setSelectedJobId(nextJobId);
                if (!nextJobId) {
                  setPipelines([]);
                  return;
                }
                void loadPipelines(nextJobId);
              }}
            >
              <option value="">Select a job to view pipeline</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-700"
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as "ats_desc" | "newest" | "updated")}
            >
              <option value="ats_desc">ATS Score (High to Low)</option>
              <option value="newest">Newest</option>
              <option value="updated">Recently Updated</option>
            </select>
            {canUpdatePipeline ? <p className="text-sm text-slate-500">Drag candidates across stages</p> : null}
            <Button
              variant="outline"
              className="h-8 px-3 text-xs"
              disabled={!selectedJobId || loading}
              onClick={() => {
                if (!selectedJobId) return;
                void loadPipelines(selectedJobId);
              }}
            >
              Refresh
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {canUpdatePipeline ? <p className="text-[12px] font-semibold text-slate-400 uppercase tracking-wide">Drag candidates to update</p> : null}
          <Button
            variant="outline"
            className="h-10 w-10 !p-0 rounded-full border-slate-200/80 bg-white shadow-sm hover:bg-slate-50 transition-all text-slate-500 hover:text-slate-800"
            disabled={!selectedJobId || loading}
            onClick={() => {
              if (!selectedJobId) return;
              void loadPipelines(selectedJobId);
            }}
            title="Refresh Pipeline"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            <span className="sr-only">Refresh</span>
          </Button>
        </div>
      </div>
      {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
      {!selectedJobId ? (
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white border border-slate-100/50 mt-6">
          <div className="py-20 flex flex-col items-center justify-center text-slate-400">
            <svg className="w-12 h-12 mb-4 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
            <p className="text-sm font-medium">Select a job to load its candidate pipeline.</p>
          </div>
        </div>
      ) : null}
      {selectedJobId && loading ? <p className="text-sm font-medium text-slate-500 mt-6">Loading pipeline...</p> : null}
      {selectedJobId && !loading && pipelines.length === 0 ? (
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white border border-slate-100/50 mt-6">
          <div className="py-20 flex flex-col items-center justify-center text-slate-400">
            <svg className="w-12 h-12 mb-4 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
            <p className="text-sm font-medium">No candidates submitted to this job yet.</p>
          </div>
        </div>
      ) : null}
      {selectedJobId && !loading && pipelines.length > 0 ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={(event) => setActivePipelineId(String(event.active.id))}
          onDragEnd={(event) => {
            void handleDragEnd(event);
          }}
          onDragCancel={() => setActivePipelineId(null)}
        >
          <div
            ref={boardScrollRef}
            className="max-w-full overflow-x-auto overscroll-x-contain pb-4 touch-pan-x [scrollbar-gutter:stable_both-edges] [scrollbar-color:rgb(148_163_184)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-400/80 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:h-2"
          >
            <div className="flex min-w-[1800px] items-start gap-6 pr-6">
              {STAGES.map((stage) => (
                <StageColumn
                  key={stage}
                  stage={stage}
                  count={grouped[stage]?.length ?? 0}
                  isDropEnabled={canUpdatePipeline}
                  activePipelineId={activePipelineId}
                >
                  {grouped[stage]?.length ? (
                    grouped[stage].map(({ pipeline, candidate }) => {
                      const ats = atsByCandidateId[normalizeCandidateId(pipeline.candidate_id)];
                      const candidateIdStr = normalizeCandidateId(pipeline.candidate_id);
                      const aiScreening = screeningsByCandidateId[candidateIdStr] ?? null;
                      return (
                        <DraggableCandidateCard
                          key={pipeline.id}
                          pipeline={pipeline}
                          candidate={candidate}
                          atsScore={ats?.score}
                          recommendation={ats?.recommendation}
                          semanticInsight={
                            ats?.ai_enrichment_status === "complete" ? ats?.recruiter_summary : null
                          }
                          aiEnrichmentStatus={ats?.ai_enrichment_status}
                          awaitingAtsMatch={!ats}
                          boardLoading={loading}
                          isTopMatch={(ats?.score ?? -1) >= 85}
                          canDrag={canUpdatePipeline && movingPipelineId === null}
                          isMoving={movingPipelineId === pipeline.id}
                          aiScreening={aiScreening}
                          onStartScreening={
                            candidate
                              ? () => setStartScreeningTarget({ pipeline, candidate })
                              : undefined
                          }
                        />
                      );
                    })
                  ) : null}
                </StageColumn>
              ))}
            </div>
          </div>
          <DragOverlay dropAnimation={null}>
            {activePipeline ? (
              <div className="w-[320px] -rotate-1 scale-105 opacity-100 shadow-[0_20px_50px_rgba(0,0,0,0.2)]">
                {(() => {
                  const ats = atsByCandidateId[normalizeCandidateId(activePipeline.candidate_id)];
                  return (
                    <CandidateCard
                      pipeline={activePipeline}
                      candidate={candidateById.get(normalizeCandidateId(activePipeline.candidate_id))}
                      atsScore={ats?.score}
                      recommendation={ats?.recommendation}
                      semanticInsight={
                        ats?.ai_enrichment_status === "complete" ? ats?.recruiter_summary : null
                      }
                      aiEnrichmentStatus={ats?.ai_enrichment_status}
                      awaitingAtsMatch={!ats}
                      boardLoading={loading}
                      isTopMatch={(ats?.score ?? -1) >= 85}
                      isMoving={false}
                    />
                  );
                })()}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      ) : null}

      {/* Start AI Screening modal */}
      {startScreeningTarget && (
        <StartScreeningModal
          candidateId={startScreeningTarget.candidate.id}
          candidateName={`${startScreeningTarget.candidate.first_name} ${startScreeningTarget.candidate.last_name}`}
          jobId={selectedJobId || undefined}
          jobTitle={jobs.find((j) => j.id === selectedJobId)?.title}
          pipelineId={startScreeningTarget.pipeline.id}
          onClose={() => setStartScreeningTarget(null)}
          onStarted={(screeningId) => {
            setStartScreeningTarget(null);
            // Refresh pipeline + screenings so the board shows updated stage + badge
            void loadPipelines(selectedJobId);
            // Navigate to screening workspace
            window.open(`/ai-screenings/${screeningId}`, "_blank");
          }}
        />
      )}
    </section>
  );
}
