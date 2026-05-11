"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  closestCorners,
  DndContext,
  DragOverlay,
  type DragEndEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getCandidates } from "@/lib/api/candidates";
import { getJobs } from "@/lib/api/jobs";
import { getJobMatchesAts, rescoreJobAts } from "@/lib/api/ats";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import { PIPELINE_UPDATE_PERMISSION, hasPermission } from "@/lib/rbac";
import type { Candidate, Job, Pipeline } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { ATSRecommendationBadge } from "@/components/ats/ats-recommendation-badge";
import { ATSScoreBadge } from "@/components/ats/ats-score-badge";
import { normalizeCandidateId } from "@/lib/ats/candidate-id";

type BoardStage = "applied" | "screening" | "interview" | "offered" | "hired";

const STAGES: BoardStage[] = ["applied", "screening", "interview", "offered", "hired"];
const STAGE_LABELS: Record<BoardStage, string> = {
  applied: "Applied",
  screening: "Screening",
  interview: "Interview",
  offered: "Offered",
  hired: "Hired",
};
const STAGE_ACCENT: Record<BoardStage, string> = {
  applied: "bg-violet-400",
  screening: "bg-sky-400",
  interview: "bg-emerald-400",
  offered: "bg-amber-400",
  hired: "bg-cyan-400",
};

function toBoardStage(stage: Pipeline["stage"]): BoardStage {
  if (stage === "offer") return "offered";
  if (stage === "placed") return "hired";
  return stage as BoardStage;
}

function toPipelineStage(stage: BoardStage): Pipeline["stage"] {
  if (stage === "offered") return "offer";
  if (stage === "hired") return "placed";
  return stage;
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
}: {
  pipeline: Pipeline;
  candidate?: Candidate;
  atsScore?: number;
  recommendation?: string;
  /** Truncated AI recruiter summary when enrichment completed. */
  semanticInsight?: string | null;
  /** From candidate_job_matches; drives compact semantic / fallback copy. */
  aiEnrichmentStatus?: string | null;
  /** No row in candidate_job_matches for this job yet (or data not loaded). */
  awaitingAtsMatch?: boolean;
  /** Full pipeline board is fetching jobs + ATS matches — do not show “pending” on every card. */
  boardLoading?: boolean;
  isMoving?: boolean;
  isTopMatch?: boolean;
}) {
  return (
    <div className={`relative group transition-transform duration-300 w-full max-w-[240px] cursor-grab active:cursor-grabbing ${isMoving ? 'opacity-70' : 'hover:-translate-y-1.5'}`}>
      <div className={`absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 opacity-0 blur transition duration-300 ${!isMoving ? 'group-hover:opacity-30' : ''}`}></div>
      <div className="relative rounded-xl bg-white p-4 text-sm border border-slate-200 shadow-sm transition-colors duration-300 group-hover:border-indigo-200/50 h-full">
        <Link href={`/candidates/${pipeline.candidate_id}`} className="block">
          <div className="mb-2.5 flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-medium text-slate-600 transition-colors duration-300 group-hover:bg-indigo-50 group-hover:text-indigo-600">
              {candidate ? `${candidate.first_name.charAt(0)}${candidate.last_name.charAt(0)}` : "?"}
            </div>
            <p className="text-sm font-medium leading-tight text-slate-900 group-hover:text-indigo-900 transition-colors duration-300">
              {candidate ? `${candidate.first_name} ${candidate.last_name}` : "Unknown candidate"}
            </p>
          </div>
          <p className="text-sm leading-snug text-slate-500">{candidate?.role ?? "Role not specified"}</p>
          <p className="mt-1.5 text-xs text-slate-400">
            Experience:{" "}
            {candidate?.years_experience !== null && candidate?.years_experience !== undefined ? `${candidate.years_experience}y` : "-"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {isTopMatch ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                Top Match
              </span>
            ) : null}
            <ATSScoreBadge
              score={atsScore}
              scorePending={Boolean(awaitingAtsMatch && !boardLoading)}
              compact
            />
            <ATSRecommendationBadge recommendation={recommendation} awaitingMatch={awaitingAtsMatch && !boardLoading} compact />
          </div>
          {semanticInsight ? (
            <p className="mt-2 line-clamp-2 text-[11px] leading-snug text-violet-800" title={semanticInsight}>
              {semanticInsight}
            </p>
          ) : aiEnrichmentStatus === "failed" ? (
            <p className="mt-2 line-clamp-2 text-[11px] leading-snug text-slate-500">
              AI semantic layer unavailable — deterministic score shown.
            </p>
          ) : null}
        </Link>
        {isMoving ? <p className="mt-2 text-xs text-blue-600">Updating stage...</p> : null}
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
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: pipeline.id,
    disabled: !canDrag,
  });

  const style = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`transition-transform duration-150 ease-out ${isDragging ? "scale-105 opacity-80 shadow-xl" : ""}`}
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
    <div className="relative group transition-transform duration-300 hover:-translate-y-1.5 cursor-default">
      <div className="absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 opacity-0 blur transition duration-300 group-hover:opacity-30"></div>
      <div
        ref={setNodeRef}
        className={`relative flex flex-col min-h-[420px] min-w-[280px] rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-200/70 transition-all duration-300 ${
          isDropTarget ? "bg-blue-50/90 ring-blue-200 shadow-md" : "group-hover:ring-indigo-200/50"
        }`}
      >
        <div className="flex-1 rounded-xl bg-slate-50 p-3">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-white/80 backdrop-blur">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className={`h-2 w-2 shrink-0 rounded-full ${STAGE_ACCENT[stage]}`} />
            <p className="truncate text-sm font-medium text-slate-800">{STAGE_LABELS[stage]}</p>
          </div>
          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
            {count}
          </span>
        </div>
        <div className="mt-3 space-y-3">
          {isDropTarget ? (
            <div className="rounded-lg bg-blue-100/60 py-2 text-center text-[11px] font-medium text-blue-600">
              Drop here
            </div>
          ) : null}
          {!count && !isDraggingAny ? <div className="h-14 rounded-lg bg-white/60" /> : null}
          {children}
        </div>
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
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

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

  function handleBoardWheel(event: React.WheelEvent<HTMLDivElement>) {
    const container = boardScrollRef.current;
    if (!container) return;
    const hasHorizontalOverflow = container.scrollWidth > container.clientWidth;
    if (!hasHorizontalOverflow) return;
    if (event.deltaY === 0) return;
    event.preventDefault();
    container.scrollLeft += event.deltaY;
  }

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
    <section className="min-w-0 space-y-6">
      <div className="mb-4 space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Pipeline Board</h1>
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
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {!selectedJobId ? (
        <Card className="rounded-xl border-slate-200 bg-white shadow-sm">
          <CardContent className="py-10 text-center text-sm text-slate-500">
            Select a job to load its candidate pipeline.
          </CardContent>
        </Card>
      ) : null}
      {selectedJobId && loading ? <p className="text-sm text-slate-600">Loading pipeline...</p> : null}
      {selectedJobId && !loading && pipelines.length === 0 ? (
        <Card className="rounded-xl border-slate-200 bg-white shadow-sm">
          <CardContent className="py-10 text-center text-sm text-slate-500">
            No candidates submitted to this job yet.
          </CardContent>
        </Card>
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
            onWheel={handleBoardWheel}
            className="max-w-full overflow-x-scroll overscroll-x-contain pb-4 touch-pan-x [scrollbar-gutter:stable_both-edges] [scrollbar-color:rgb(148_163_184)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-400/80 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:h-2"
          >
            <div className="flex min-w-[1500px] items-start gap-6 pr-6">
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
                        />
                      );
                    })
                  ) : null}
                </StageColumn>
              ))}
            </div>
          </div>
          <DragOverlay>
            {activePipeline ? (
              <div className="w-[260px] rotate-1 scale-105 opacity-95 shadow-xl">
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
    </section>
  );
}
