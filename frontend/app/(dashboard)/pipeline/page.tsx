"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
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
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import { PIPELINE_UPDATE_PERMISSION, hasPermission } from "@/lib/rbac";
import type { Candidate, Job, Pipeline } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";

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
  isMoving,
}: {
  pipeline: Pipeline;
  candidate?: Candidate;
  isMoving?: boolean;
}) {
  return (
    <div
      className={`rounded-xl bg-white p-4 text-sm shadow-sm transition duration-200 ${
        isMoving ? "opacity-70" : "hover:scale-[1.02] hover:shadow-md"
      } w-full max-w-[240px] cursor-grab active:cursor-grabbing hover:ring-1 hover:ring-slate-200`}
    >
      <Link href={`/candidates/${pipeline.candidate_id}`} className="block">
        <div className="mb-2.5 flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-medium text-slate-600">
            {candidate ? `${candidate.first_name.charAt(0)}${candidate.last_name.charAt(0)}` : "?"}
          </div>
          <p className="text-sm font-medium leading-tight text-slate-900">
            {candidate ? `${candidate.first_name} ${candidate.last_name}` : "Unknown candidate"}
          </p>
        </div>
        <p className="text-sm leading-snug text-slate-500">{candidate?.role ?? "Role not specified"}</p>
        <p className="mt-1.5 text-xs text-slate-400">
          Experience:{" "}
          {candidate?.years_experience !== null && candidate?.years_experience !== undefined ? `${candidate.years_experience}y` : "-"}
        </p>
      </Link>
      {isMoving ? <p className="mt-1 text-xs text-blue-600">Updating stage...</p> : null}
    </div>
  );
}

function DraggableCandidateCard({
  pipeline,
  candidate,
  canDrag,
  isMoving,
}: {
  pipeline: Pipeline;
  candidate?: Candidate;
  canDrag: boolean;
  isMoving: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useDraggable({
    id: pipeline.id,
    disabled: !canDrag,
  });

  const style = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`transition-transform duration-150 ease-out ${isDragging ? "scale-105 opacity-80 shadow-xl" : ""}`}
      {...attributes}
      {...listeners}
    >
      <CandidateCard pipeline={pipeline} candidate={candidate} isMoving={isMoving} />
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
    <div
      ref={setNodeRef}
      className={`min-h-[420px] min-w-[280px] rounded-xl bg-white/70 p-3 shadow-sm ring-1 ring-slate-200/70 transition duration-200 ${
        isDropTarget ? "bg-blue-50/90 ring-blue-200 shadow-md" : "hover:bg-slate-100/40"
      }`}
    >
      <div className="rounded-xl bg-slate-50 p-3">
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
  const canUpdatePipeline = hasPermission(permissions, PIPELINE_UPDATE_PERMISSION);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [candidateData, jobData] = await Promise.all([getCandidates(500, 0, { status: "active" }), getJobs(200, 0)]);
        setCandidates(candidateData);
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
  }, []);

  async function loadPipelines(jobId: string) {
    setLoading(true);
    setError(null);
    try {
      const pipelineData = await getPipelines(200, 0, jobId);
      console.info("[pipeline-board] fetched", { jobId, count: pipelineData.length });
      setPipelines(pipelineData);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load pipeline board.");
      }
    } finally {
      setLoading(false);
    }
  }

  const grouped = useMemo(() => {
    const candidateMap = new Map(candidates.map((candidate) => [candidate.id, candidate]));
    return STAGES.reduce<Record<BoardStage, Array<{ pipeline: Pipeline; candidate: Candidate | undefined }>>>((acc, stage) => {
      acc[stage] = pipelines
        .filter((pipeline) => toBoardStage(pipeline.stage) === stage)
        .map((pipeline) => ({ pipeline, candidate: candidateMap.get(pipeline.candidate_id) }));
      return acc;
    }, {} as Record<BoardStage, Array<{ pipeline: Pipeline; candidate: Candidate | undefined }>>);
  }, [candidates, pipelines]);

  const pipelineById = useMemo(() => new Map(pipelines.map((pipeline) => [pipeline.id, pipeline])), [pipelines]);
  const candidateById = useMemo(() => new Map(candidates.map((candidate) => [candidate.id, candidate])), [candidates]);
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
    <section className="space-y-6">
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
          {canUpdatePipeline ? <p className="text-sm text-slate-500">Drag candidates across stages</p> : null}
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
          <div className="overflow-x-auto pb-3 [scrollbar-color:rgb(203_213_225)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300/70 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:h-1.5">
            <div className="flex min-w-max items-start gap-6 pr-4">
              {STAGES.map((stage) => (
                <StageColumn
                  key={stage}
                  stage={stage}
                  count={grouped[stage]?.length ?? 0}
                  isDropEnabled={canUpdatePipeline}
                  activePipelineId={activePipelineId}
                >
                  {grouped[stage]?.length ? (
                    grouped[stage].map(({ pipeline, candidate }) => (
                      <DraggableCandidateCard
                        key={pipeline.id}
                        pipeline={pipeline}
                        candidate={candidate}
                        canDrag={canUpdatePipeline && movingPipelineId === null}
                        isMoving={movingPipelineId === pipeline.id}
                      />
                    ))
                  ) : null}
                </StageColumn>
              ))}
            </div>
          </div>
          <DragOverlay>
            {activePipeline ? (
              <div className="w-[260px] rotate-1 scale-105 opacity-95 shadow-xl">
                <CandidateCard
                  pipeline={activePipeline}
                  candidate={candidateById.get(activePipeline.candidate_id)}
                  isMoving={false}
                />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      ) : null}
    </section>
  );
}
