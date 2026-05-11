"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, API_BASE_URL } from "@/lib/api/client";
import { getMyPermissions } from "@/lib/api/auth";
import {
  addCandidateInteraction,
  assignCandidateRecruiter,
  createCandidateInterview,
  getCandidateById,
  getCandidateInteractions,
  getCandidateInterviews,
  updateCandidate,
  updateCandidateInterview,
  type CandidateInteraction,
  type InterviewRecord,
} from "@/lib/api/candidates";
import { getJobs, submitCandidateToJob } from "@/lib/api/jobs";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import {
  atsAwaitingSemanticEnrichment,
  getCandidateMatchesAts,
  pollAtsPairStatusesUntilSettled,
  pollCandidateMatchesUntilEnriched,
  rescoreCandidateAts,
} from "@/lib/api/ats";
import type { Candidate, CandidateMatchEntry, Job, OrganizationUser, Pipeline } from "@/lib/api/types";
import { getUsers } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Mail, Phone, MapPin, Briefcase, Calendar, FileText, Download, ExternalLink, MessageSquare, Clock, ArrowLeft, Edit3, Save, X, Plus, User, Star, Sparkles, Layers , Activity, Brain} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { ATSRecommendationBadge } from "@/components/ats/ats-recommendation-badge";
import { ATSScoreBadge } from "@/components/ats/ats-score-badge";
import { ATSMatchBreakdownPanel } from "@/components/ats/ats-match-breakdown-panel";


function snapJobIdsFromMatches(matches: CandidateMatchEntry[]): string[] {
  return matches.map((m) => m.job_id).filter(Boolean);
}

export default function CandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [interactions, setInteractions] = useState<CandidateInteraction[]>([]);
  const [interactionsLoadFailed, setInteractionsLoadFailed] = useState(false);
  const [interviews, setInterviews] = useState<InterviewRecord[]>([]);
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [role, setRole] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [newNote, setNewNote] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [interviewerName, setInterviewerName] = useState("");
  const [interviewType, setInterviewType] = useState<"HR" | "TECH">("HR");
  const [feedbackNotes, setFeedbackNotes] = useState<Record<string, string>>({});
  const [feedbackRatings, setFeedbackRatings] = useState<Record<string, string>>({});
  const [rescheduleTimes, setRescheduleTimes] = useState<Record<string, string>>({});
  const [interviewUpdatingId, setInterviewUpdatingId] = useState<string | null>(null);
  const [selectedRecruiterId, setSelectedRecruiterId] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [submitJobId, setSubmitJobId] = useState("");
  const [submittingToJob, setSubmittingToJob] = useState(false);
  const [updatingPipelineId, setUpdatingPipelineId] = useState<string | null>(null);
  const [atsMatches, setAtsMatches] = useState<CandidateMatchEntry[]>([]);
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsRescoreBusy, setAtsRescoreBusy] = useState(false);
  const [atsHint, setAtsHint] = useState<string | null>(null);
  const candidateLoadSeqRef = useRef(0);
  const atsSemanticInFlight = useMemo(() => atsAwaitingSemanticEnrichment(atsMatches), [atsMatches]);

  async function loadCandidateMatchesWithRetry(
    candidateId: string,
    loadSeq: number,
    attempts = 4,
    waitMs = 1200
  ): Promise<CandidateMatchEntry[]> {
    for (let i = 0; i < attempts; i++) {
      try {
        const result = await getCandidateMatchesAts(candidateId, { limit: 50, offset: 0 });
        if (loadSeq !== candidateLoadSeqRef.current) {
          return [];
        }
        if (result.matches.length > 0) {
          return result.matches;
        }
      } catch {
        // Transient or permission noise; retry a few times after rescoring.
      }
      if (i < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      }
    }
    return [];
  }

  useEffect(() => {
    if (!params.candidateId) {
      return;
    }
    const loadSeq = ++candidateLoadSeqRef.current;
    async function loadData() {
      try {
        setInteractionsLoadFailed(false);
        const data = await getCandidateById(params.candidateId);
        const [timelineResult, pipelinesResult, interviewResult] = await Promise.allSettled([
          getCandidateInteractions(params.candidateId, 100, 0),
          getPipelines(200, 0, undefined, params.candidateId),
          getCandidateInterviews(params.candidateId),
        ]);
        setAtsLoading(true);
        setAtsHint(null);
        let initialMatches: CandidateMatchEntry[] = [];
        try {
          const first = await getCandidateMatchesAts(params.candidateId, { limit: 50, offset: 0 });
          initialMatches = first.matches ?? [];
          setAtsHint(first.ats_hint ?? null);
        } catch {
          initialMatches = [];
          setAtsHint(null);
        }
        if (loadSeq !== candidateLoadSeqRef.current) {
          return;
        }
        setCandidate(data);
        setInteractionsLoadFailed(timelineResult.status === "rejected");
        setInteractions(timelineResult.status === "fulfilled" ? timelineResult.value : []);
        const loadedPipelines = pipelinesResult.status === "fulfilled" ? pipelinesResult.value : [];
        setPipelines(loadedPipelines);
        setInterviews(interviewResult.status === "fulfilled" ? interviewResult.value : []);
        setAtsMatches(initialMatches);
        if (initialMatches.length === 0 && loadedPipelines.length > 0) {
          // ATS scoring is async; trigger once and poll briefly before showing unavailable.
          await rescoreCandidateAts(params.candidateId).catch(() => undefined);
          if (loadSeq !== candidateLoadSeqRef.current) {
            return;
          }
          const retried = await loadCandidateMatchesWithRetry(params.candidateId, loadSeq, 4, 1200);
          if (retried.length > 0) {
            setAtsMatches(retried);
          }
        }
        setFirstName(data.first_name);
        setLastName(data.last_name);
        setEmail(data.email);
        setPhone(data.phone ?? "");
        setLocation(data.location ?? "");
        setRole(data.role ?? "");
        setYearsExperience(data.years_experience !== null && data.years_experience !== undefined ? String(data.years_experience) : "");
        setSelectedRecruiterId(data.recruiter_id ?? "");
        setError(null);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load candidate details");
        }
      }
      finally {
        if (loadSeq === candidateLoadSeqRef.current) {
          setAtsLoading(false);
        }
      }
    }
    void loadData();
  }, [params.candidateId]);

  useEffect(() => {
    async function loadUsers() {
      try {
        const me = await getMyPermissions();
        if (!me.permissions.includes("users:invite")) {
          setUsers([]);
          return;
        }
        const data = await getUsers();
        setUsers(data.filter((user) => user.role === "recruiter" || user.role === "admin"));
      } catch {
        setUsers([]);
      }
    }
    async function loadJobs() {
      try {
        const data = await getJobs(50, 0);
        setJobs(data);
      } catch {
        setJobs([]);
      }
    }
    loadUsers();
    loadJobs();
  }, []);

  const interviewMetaById = useMemo(() => {
    const meta = new Map<string, { interview_type?: string; rating?: number; notes?: string }>();
    for (const item of interactions) {
      if (item.interaction_type !== "interview" || !item.metadata) continue;
      const interviewId = typeof item.metadata.interview_id === "string" ? item.metadata.interview_id : null;
      if (!interviewId) continue;
      meta.set(interviewId, {
        interview_type: typeof item.metadata.interview_type === "string" ? item.metadata.interview_type : undefined,
        rating: typeof item.metadata.rating === "number" ? item.metadata.rating : undefined,
        notes: item.body ?? undefined,
      });
    }
    return meta;
  }, [interactions]);

  const orderedTimeline = useMemo(
    () =>
      [...interactions].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      ),
    [interactions]
  );

  const resumeUrl = useMemo(() => {
    if (!candidate?.resume_s3_key) return null;
    if (/^https?:\/\//.test(candidate.resume_s3_key)) return candidate.resume_s3_key;
    return `${API_BASE_URL}/candidate-management/candidates/${params.candidateId}/resume`;
  }, [candidate?.resume_s3_key, params.candidateId]);

  const handleResumeAction = async (action: "open" | "download") => {
    if (!resumeUrl) return;

    // If it's a direct external link (e.g. S3), just open it
    if (/^https?:\/\//.test(resumeUrl) && !resumeUrl.includes("/candidate-management/")) {
      window.open(resumeUrl, "_blank", "noopener,noreferrer");
      return;
    }

    try {
      const orgId = localStorage.getItem("airis_organization_id");
      const fileName = (candidate?.resume_file_name || "").toLowerCase();
      const isDocx = fileName.endsWith(".docx");
      const isDoc = fileName.endsWith(".doc");

      if (action === "open" && isDocx) {
        const docxUrl = `${resumeUrl}${resumeUrl.includes("?") ? "&" : "?"}disposition=attachment`;
        const docxRes = await fetch(docxUrl, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("airis_access_token")}`,
            ...(orgId ? { "X-Workspace-Id": orgId } : {}),
          },
        });
        if (!docxRes.ok) throw new Error("Failed to load DOCX resume");
        const arrayBuffer = await docxRes.arrayBuffer();

        const previewWin = window.open("", "_blank");
        if (!previewWin) {
          throw new Error("Popup blocked. Please allow popups for resume preview.");
        }
        previewWin.document.write(
          "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
          + "<title>Resume Preview</title>"
          + "<style>"
          + "body{margin:0;background:#f8fafc;font-family:Inter,Segoe UI,Arial,sans-serif;}"
          + ".viewer-shell{max-width:980px;margin:20px auto;padding:0 12px;}"
          + ".docx-wrapper{background:transparent;padding:0 !important;}"
          + ".docx{background:#fff !important;border:1px solid #e2e8f0;border-radius:12px;padding:28px !important;box-shadow:0 1px 2px rgba(0,0,0,.04);}"
          + "</style>"
          + "</head><body><div id='docx'></div></body></html>"
        );
        previewWin.document.close();
        const container = previewWin.document.getElementById("docx");
        if (!container) throw new Error("Failed to initialize preview container.");
        container.className = "viewer-shell";

        const { renderAsync } = await import("docx-preview");
        await renderAsync(arrayBuffer, container, previewWin.document.head, {
          className: "docx",
          inWrapper: true,
          ignoreWidth: true,
          ignoreHeight: true,
          breakPages: false,
          ignoreFonts: false,
        });
        return;
      }

      if (action === "open" && isDoc) {
        const previewUrl = `${API_BASE_URL}/candidate-management/candidates/${params.candidateId}/resume/preview`;
        const previewRes = await fetch(previewUrl, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("airis_access_token")}`,
            ...(orgId ? { "X-Workspace-Id": orgId } : {}),
          },
        });
        if (!previewRes.ok) throw new Error("Failed to preview resume");
        const preview = await previewRes.json() as { file_name: string; html: string };
        const htmlBlob = new Blob(
          [preview.html],
          { type: "text/html" }
        );
        window.open(window.URL.createObjectURL(htmlBlob), "_blank", "noopener,noreferrer");
        return;
      }

      const targetUrl = `${resumeUrl}${resumeUrl.includes("?") ? "&" : "?"}disposition=${action === "open" ? "inline" : "attachment"}`;
      const response = await fetch(targetUrl, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("airis_access_token")}`,
          ...(orgId ? { "X-Workspace-Id": orgId } : {}),
        },
      });
      if (!response.ok) throw new Error("Failed to access resume");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      if (action === "download") {
        const a = document.createElement("a");
        a.href = url;
        a.download = candidate?.resume_file_name || "resume.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        window.open(url, "_blank", "noopener,noreferrer");
      }

      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.error(err);
      alert("Error accessing resume file");
    }
  };

  function formatPipelineStage(stage: Pipeline["stage"]) {
    if (stage === "offer") return "Offered";
    if (stage === "placed") return "Hired";
    return `${stage.charAt(0).toUpperCase()}${stage.slice(1)}`;
  }

  const sortedPipelines = useMemo(
    () =>
      [...pipelines].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    [pipelines]
  );

  const currentPipeline = sortedPipelines[0];
  const stageLabel = currentPipeline ? formatPipelineStage(currentPipeline.stage).toUpperCase() : "NOT SUBMITTED";
  const recruiterName = users.find((user) => user.id === candidate?.recruiter_id)?.email ?? candidate?.recruiter_id ?? "-";
  const candidateJobId = currentPipeline?.job_id ?? null;
  const jobTitle = jobs.find((job) => job.id === candidateJobId)?.title ?? (candidateJobId || "-");

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!candidate) {
    return <p className="text-sm text-slate-600">Loading candidate...</p>;
  }

  async function handleSave() {
    if (!params.candidateId) {
      return;
    }
    setIsSaving(true);
    try {
      const updated = await updateCandidate(params.candidateId, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        location: location.trim() || undefined,
        headline: role.trim() || undefined,
        years_experience: yearsExperience.trim() ? Number(yearsExperience.trim()) : undefined,
      });
      setCandidate(updated);
      setIsEditing(false);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unable to update candidate.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  function handleCancel() {
    if (!candidate) {
      return;
    }
    setIsEditing(false);
    setFirstName(candidate.first_name);
    setLastName(candidate.last_name);
    setEmail(candidate.email);
    setPhone(candidate.phone ?? "");
    setLocation(candidate.location ?? "");
    setRole(candidate.role ?? "");
    setYearsExperience(
      candidate.years_experience !== null && candidate.years_experience !== undefined ? String(candidate.years_experience) : ""
    );
  }

  async function handleAddNote() {
    if (!params.candidateId || !newNote.trim()) return;
    setAddingNote(true);
    try {
      await addCandidateInteraction(params.candidateId, {
        interaction_type: "note",
        title: "Candidate note",
        body: newNote.trim(),
      });
      const timeline = await getCandidateInteractions(params.candidateId, 100, 0);
      setInteractions(timeline);
      setNewNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add note.");
    } finally {
      setAddingNote(false);
    }
  }

  async function handleScheduleInterview() {
    if (!params.candidateId || !scheduledAt || !candidate) return;
    await createCandidateInterview({
      candidate_id: params.candidateId,
      job_id: candidate.job_id ?? undefined,
      scheduled_at: new Date(scheduledAt).toISOString(),
      interviewer_name: interviewerName || undefined,
      interview_type: interviewType,
      status: "scheduled",
    });
    const [timeline, interviewList] = await Promise.all([
      getCandidateInteractions(params.candidateId, 100, 0),
      getCandidateInterviews(params.candidateId),
    ]);
    setInteractions(timeline);
    setInterviews(interviewList);
    setScheduledAt("");
    setInterviewerName("");
  }

  async function refreshInterviewData() {
    if (!params.candidateId) return;
    const [timeline, interviewList] = await Promise.all([
      getCandidateInteractions(params.candidateId, 100, 0),
      getCandidateInterviews(params.candidateId),
    ]);
    setInteractions(timeline);
    setInterviews(interviewList);
  }

  async function handleReschedule(interviewId: string) {
    const scheduledAt = rescheduleTimes[interviewId];
    if (!scheduledAt) return;
    setInterviewUpdatingId(interviewId);
    try {
      await updateCandidateInterview(interviewId, {
        scheduled_at: new Date(scheduledAt).toISOString(),
        status: "rescheduled",
      });
      await updateCandidateInterview(interviewId, { status: "scheduled" });
      await refreshInterviewData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reschedule interview.");
    } finally {
      setInterviewUpdatingId(null);
    }
  }

  async function handleCancelInterview(interviewId: string) {
    setInterviewUpdatingId(interviewId);
    try {
      await updateCandidateInterview(interviewId, { status: "cancelled" });
      await refreshInterviewData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel interview.");
    } finally {
      setInterviewUpdatingId(null);
    }
  }

  async function handleSaveFeedback(interviewId: string) {
    setInterviewUpdatingId(interviewId);
    try {
      const ratingValue = Number.parseInt(feedbackRatings[interviewId] ?? "", 10);
      await updateCandidateInterview(interviewId, {
        notes: feedbackNotes[interviewId] || undefined,
        rating: Number.isNaN(ratingValue) ? undefined : ratingValue,
        status: "completed",
      });
      await refreshInterviewData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save interview feedback.");
    } finally {
      setInterviewUpdatingId(null);
    }
  }

  async function handleAssignRecruiter() {
    if (!params.candidateId || !selectedRecruiterId) return;
    const previous = candidate?.recruiter_id ?? null;
    setCandidate((prev) => (prev ? { ...prev, recruiter_id: selectedRecruiterId } : prev));
    try {
      const updated = await assignCandidateRecruiter(params.candidateId, selectedRecruiterId);
      setCandidate(updated);
    } catch (err) {
      setCandidate((prev) => (prev ? { ...prev, recruiter_id: previous } : prev));
      setError(err instanceof Error ? err.message : "Unable to assign recruiter.");
    }
  }

  async function handleSubmitToJob() {
    if (!candidate || !submitJobId) return;
    const duplicate = pipelines.some((item) => item.candidate_id === candidate.id && item.job_id === submitJobId);
    if (duplicate) {
      setError("Candidate is already submitted to this job.");
      return;
    }
    setSubmittingToJob(true);
    try {
      await submitCandidateToJob(submitJobId, candidate.id);
      try {
        const linkedPipelines = await getPipelines(200, 0, undefined, candidate.id);
        setPipelines(linkedPipelines);
      } catch {
        setPipelines([]);
      }
      try {
        const fresh = await getCandidateMatchesAts(candidate.id, { limit: 50, offset: 0 });
        setAtsMatches(fresh.matches);
      } catch {
        // ATS can lag behind async scoring briefly.
      }
      setSubmitJobId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit candidate to job.");
    } finally {
      setSubmittingToJob(false);
    }
  }

  async function handleQuickStageUpdate(pipelineId: string, nextStage: Pipeline["stage"]) {
    if (!candidate) return;
    setUpdatingPipelineId(pipelineId);
    try {
      await updatePipeline(pipelineId, { stage: nextStage });
      const linkedPipelines = await getPipelines(200, 0, undefined, candidate.id);
      setPipelines(linkedPipelines);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update pipeline stage.");
    } finally {
      setUpdatingPipelineId(null);
    }
  }

  async function handleRescoreAts() {
    if (!params.candidateId) return;
    const loadSeq = candidateLoadSeqRef.current;
    if (atsSemanticInFlight || atsRescoreBusy) return;
    setAtsRescoreBusy(true);
    setError(null);
    try {
      const meta = await rescoreCandidateAts(params.candidateId);
      try {
        const snap = await getCandidateMatchesAts(params.candidateId, { limit: 50, offset: 0 });
        if (loadSeq === candidateLoadSeqRef.current) {
          setAtsMatches(snap.matches ?? []);
        }
      } catch {
        const fallback = await loadCandidateMatchesWithRetry(params.candidateId, loadSeq, 4, 800);
        if (loadSeq === candidateLoadSeqRef.current) {
          setAtsMatches(fallback);
        }
      }
      if (loadSeq === candidateLoadSeqRef.current && meta.semantic_enrichment === "queued") {
        const pairJobIds = Array.from(
          new Set([
            ...snapJobIdsFromMatches(atsMatches),
            ...pipelines.map((p) => p.job_id),
          ])
        );
        if (pairJobIds.length > 0) {
          await pollAtsPairStatusesUntilSettled(
            pairJobIds.map((jobId) => ({ candidate_id: params.candidateId, job_id: jobId })),
          );
        } else {
          await pollCandidateMatchesUntilEnriched(params.candidateId, {
            onTick: (m) => {
              if (loadSeq !== candidateLoadSeqRef.current) return;
              setAtsMatches(m);
            },
          });
        }
        const refreshed = await getCandidateMatchesAts(params.candidateId, { limit: 50, offset: 0 });
        if (loadSeq === candidateLoadSeqRef.current) {
          setAtsMatches(refreshed.matches ?? []);
        }
      }
    } catch {
      if (loadSeq === candidateLoadSeqRef.current) {
        setError("ATS rescore failed. Wait a few seconds and try again.");
      }
    } finally {
      if (loadSeq === candidateLoadSeqRef.current) {
        setAtsRescoreBusy(false);
      }
    }
  }


  return (
    <section className="mx-auto max-w-5xl space-y-6 pb-12">
      <div className="flex items-center justify-between mb-2">
        <Link href="/candidates" className="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" /> Back to Candidates
        </Link>
        <span className={cn(
          "rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider",
          stageLabel === "Hired" ? "bg-green-100 text-green-700" :
          stageLabel === "Rejected" ? "bg-red-100 text-red-700" :
          "bg-orange-100 text-[#FF5A1F]"
        )}>
          {stageLabel}
        </span>
      </div>

      {/* Header Profile Card */}
      <div className="bg-white p-6 md:p-8 rounded-xl shadow-sm border border-gray-200">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex items-start gap-5 flex-1 min-w-0">
            <div className="h-16 w-16 rounded-full bg-orange-100 flex items-center justify-center text-[#FF5A1F] text-2xl font-bold shrink-0">
              {candidate.first_name?.[0]}{candidate.last_name?.[0]}
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-bold text-gray-900 truncate">
                {candidate.first_name} {candidate.last_name}
              </h1>
              <p className="text-sm text-gray-500 font-medium flex items-center gap-2 mt-1 truncate">
                <Briefcase className="w-4 h-4 shrink-0" /> <span className="truncate">{candidate.role ?? "Role not specified"}</span>
              </p>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-3 text-sm text-gray-600">
                {candidate.email && (
                  <a href={`mailto:${candidate.email}`} className="flex items-center gap-1.5 hover:text-[#FF5A1F] transition-colors truncate max-w-full">
                    <Mail className="w-4 h-4 shrink-0" /> <span className="truncate">{candidate.email}</span>
                  </a>
                )}
                {candidate.phone && (
                  <a href={`tel:${candidate.phone}`} className="flex items-center gap-1.5 hover:text-[#FF5A1F] transition-colors shrink-0">
                    <Phone className="w-4 h-4 shrink-0" /> {candidate.phone}
                  </a>
                )}
                {candidate.location && (
                  <span className="flex items-center gap-1.5 truncate max-w-full">
                    <MapPin className="w-4 h-4 shrink-0" /> <span className="truncate">{candidate.location}</span>
                  </span>
                )}
                {jobTitle !== "-" && (
                  <span className="flex items-center gap-1.5 text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded-md shrink-0">
                    <Briefcase className="w-3.5 h-3.5 shrink-0" /> {jobTitle}
                  </span>
                )}
              </div>
            </div>
          </div >

    <div className="flex flex-col gap-3 w-full md:w-[320px] shrink-0">
      <div className="flex flex-col space-y-2">
        <label className="text-xs font-semibold text-gray-500 uppercase">Submit to Job</label>
        <div className="flex items-center gap-2">
          <select
            className="flex-1 w-full min-w-0 truncate rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] outline-none transition-all bg-white"
            value={submitJobId}
            onChange={(event) => setSubmitJobId(event.target.value)}
          >
            <option value="">Select job...</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>{job.title}</option>
            ))}
          </select>
          <Button
            onClick={handleSubmitToJob}
            disabled={!submitJobId || submittingToJob}
            className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm shrink-0"
          >
            {submittingToJob ? "..." : "Submit"}
          </Button>
        </div>
      </div>
    </div>
        </div >
      </div >

    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Column: Details & Resume */}
      <div className="lg:col-span-2 space-y-6">
        {/* Detailed Profile */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5 flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <User className="w-4 h-4 text-[#FF5A1F]" /> Profile Details
            </h2>
            {isEditing ? (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCancel} disabled={isSaving} className="h-8 text-xs">
                  <X className="w-3 h-3 mr-1" /> Cancel
                </Button>
                <Button size="sm" onClick={handleSave} disabled={isSaving} className="h-8 text-xs bg-[#FF5A1F] hover:bg-[#E54E1A] text-white">
                  <Save className="w-3 h-3 mr-1" /> {isSaving ? "Saving..." : "Save"}
                </Button>
              </div>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setIsEditing(true)} className="h-8 text-xs bg-white border-gray-200 hover:bg-gray-50 text-gray-700">
                <Edit3 className="w-3 h-3 mr-1" /> Edit
              </Button>
            )}
          </div>

          <div className="p-6">
            {isEditing ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">First Name</label><Input value={firstName} onChange={(e) => setFirstName(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Last Name</label><Input value={lastName} onChange={(e) => setLastName(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Email</label><Input value={email} onChange={(e) => setEmail(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Phone</label><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Location</label><Input value={location} onChange={(e) => setLocation(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Role</label><Input value={role} onChange={(e) => setRole(e.target.value)} /></div>
                <div className="space-y-1.5"><label className="text-xs font-medium text-gray-500">Years Experience</label><Input type="number" min={0} value={yearsExperience} onChange={(e) => setYearsExperience(e.target.value)} /></div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-6 gap-x-4">
                <div><p className="text-xs font-medium text-gray-500 mb-1">Email</p><p className="text-sm font-medium text-gray-900">{candidate.email}</p></div>
                <div><p className="text-xs font-medium text-gray-500 mb-1">Phone</p><p className="text-sm font-medium text-gray-900">{candidate.phone || "-"}</p></div>
                <div><p className="text-xs font-medium text-gray-500 mb-1">Location</p><p className="text-sm font-medium text-gray-900">{candidate.location || "-"}</p></div>
                <div><p className="text-xs font-medium text-gray-500 mb-1">Role</p><p className="text-sm font-medium text-gray-900">{candidate.role || "-"}</p></div>
                <div><p className="text-xs font-medium text-gray-500 mb-1">Experience</p><p className="text-sm font-medium text-gray-900">{candidate.years_experience != null ? `${candidate.years_experience} years` : "-"}</p></div>

                {candidate.experience_summary && (
                  <div className="md:col-span-2">
                    <p className="text-xs font-medium text-gray-500 mb-1">Experience Summary</p>
                    <p className="text-sm text-gray-800 leading-relaxed bg-gray-50 p-4 rounded-lg">{candidate.experience_summary}</p>
                  </div>
                )}
                {candidate.education && (
                  <div className="md:col-span-2">
                    <p className="text-xs font-medium text-gray-500 mb-1">Education</p>
                    <p className="text-sm text-gray-800">{candidate.education}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Resume */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#FF5A1F]" /> Resume
            </h2>
          </div>
          <div className="p-6">
            {candidate.resume_file_name || candidate.resume_s3_key ? (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4 mb-4 sm:mb-0">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-50 text-[#FF5A1F]">
                    <FileText className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{candidate.resume_file_name ?? "Resume Document"}</p>
                    <p className="text-xs text-gray-500">PDF Document</p>
                  </div>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  {candidate.resume_s3_key ? (
                    <>
                      <Button variant="outline" className="flex-1 sm:flex-none border-gray-200 hover:bg-gray-50 hover:text-gray-900" onClick={() => handleResumeAction("open")}>
                        <ExternalLink className="w-4 h-4 mr-2" /> Open
                      </Button>
                      <Button className="flex-1 sm:flex-none bg-slate-900 hover:bg-slate-800 text-white" onClick={() => handleResumeAction("download")}>
                        <Download className="w-4 h-4 mr-2" /> Download
                      </Button>
                    </>
                  ) : (
                    <span className="text-xs font-medium text-gray-400 bg-gray-50 px-3 py-1.5 rounded-md border border-gray-100">File unavailable</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 px-4 rounded-xl border-2 border-dashed border-gray-200 bg-gray-50">
                <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-gray-900">No resume available</p>
                <p className="text-xs text-gray-500 mt-1">This candidate was added manually or the file is missing.</p>
              </div>
            )}
          </div>
        </div>

        {/* Applied Jobs */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-[#FF5A1F]" /> Applied Jobs
            </h2>
          </div>
          <div className="p-0">
            {sortedPipelines.length === 0 ? (
              <div className="p-8 text-center">
                <Briefcase className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No jobs applied yet.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-gray-50/50 border-b border-gray-100">
                    <tr>
                      <th className="px-6 py-3 font-medium text-gray-500 uppercase text-xs tracking-wider">Job Title</th>
                      <th className="px-6 py-3 font-medium text-gray-500 uppercase text-xs tracking-wider">Current Stage</th>
                      <th className="px-6 py-3 font-medium text-gray-500 uppercase text-xs tracking-wider text-right">Last Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sortedPipelines.map((pipeline) => (
                      <tr key={pipeline.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-4 font-medium text-gray-900">
                          {jobs.find((job) => job.id === pipeline.job_id)?.title ?? pipeline.job_id}
                        </td>
                        <td className="px-6 py-4">
                          <select
                            className={cn(
                              "rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider outline-none border transition-colors",
                              pipeline.stage === "placed" ? "bg-green-50 border-green-200 text-green-700" :
                                pipeline.stage === "offer" ? "bg-indigo-50 border-indigo-200 text-indigo-700" :
                                  pipeline.stage === "interview" ? "bg-blue-50 border-blue-200 text-blue-700" :
                                    "bg-gray-50 border-gray-200 text-gray-700 hover:border-gray-300 focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F]"
                            )}
                            value={pipeline.stage}
                            onChange={(event) => void handleQuickStageUpdate(pipeline.id, event.target.value as Pipeline["stage"])}
                            disabled={updatingPipelineId === pipeline.id}
                          >
                            <option value="applied">Applied</option>
                            <option value="screening">Screening</option>
                            <option value="interview">Interview</option>
                            <option value="offer">Offered</option>
                            <option value="placed">Hired</option>
                          </select>
                        </td>
                        <td className="px-6 py-4 text-xs text-gray-500 text-right">
                          {new Date(pipeline.updated_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
        
        {/* ATS Match Breakdown */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#FF5A1F]" /> ATS Match Breakdown
            </h2>
          </div>
          <div className="p-6 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <ATSScoreBadge
                  score={atsMatches[0]?.fit_score}
                  isLoading={atsLoading || atsRescoreBusy}
                  scorePending={!atsLoading && !atsRescoreBusy && atsMatches.length === 0 && pipelines.length > 0}
                />
                <ATSRecommendationBadge
                  recommendation={atsMatches[0]?.recommendation}
                  isLoading={atsLoading || atsRescoreBusy}
                  awaitingMatch={!atsLoading && !atsRescoreBusy && atsMatches.length === 0 && pipelines.length > 0}
                />
              </div>
              <Button
                variant="outline"
                onClick={() => void handleRescoreAts()}
                disabled={atsRescoreBusy || atsSemanticInFlight}
              >
                {atsRescoreBusy ? "Rescoring…" : atsSemanticInFlight ? "AI enrichment…" : "Rescore ATS"}
              </Button>
            </div>
            {atsLoading ? (
              <div className="space-y-2 text-slate-500">
                <div className="h-3 w-48 animate-pulse rounded bg-slate-100" />
                <div className="h-24 animate-pulse rounded-lg border border-slate-100 bg-slate-50/80" />
              </div>
            ) : atsRescoreBusy && atsMatches.length === 0 ? (
              <p className="text-slate-500">Saving baseline scores…</p>
            ) : atsMatches.length === 0 ? (
              <div className="space-y-2 text-slate-500">
                <p>
                  {pipelines.length > 0
                    ? "No scored rows in candidate_job_matches yet — ATS runs after resume parse and job submit."
                    : "No job applications yet — submit this candidate to a job to generate ATS scores."}
                </p>
                {atsHint === "NO_SCORE_ROWS_YET" && pipelines.length > 0 ? (
                  <p className="text-amber-800">
                    ATS scores are still missing after waiting. Check backend logs for{" "}
                    <code className="rounded bg-slate-100 px-1">ats.rescore</code> /{" "}
                    <code className="rounded bg-slate-100 px-1">ats.task.failed</code>, confirm Celery or the in-process
                    fallback ran, then use “Rescore ATS” or re-open this page.
                  </p>
                ) : null}
              </div>
            ) : (
              atsMatches.map((match) => (
                <ATSMatchBreakdownPanel
                  key={match.job_id}
                  title={jobs.find((job) => job.id === match.job_id)?.title ?? match.job_id}
                  isLoading={false}
                  data={{
                    fit_score: match.fit_score,
                    deterministic_match_score: match.deterministic_match_score,
                    semantic_match_score: match.semantic_match_score,
                    ai_enrichment_status: match.ai_enrichment_status,
                    ats_pipeline_status: match.ats_pipeline_status,
                    enrichment_error: match.enrichment_error,
                    deterministic_completed_at: match.deterministic_completed_at,
                    semantic_completed_at: match.semantic_completed_at,
                    recruiter_summary: match.recruiter_summary,
                    confidence_reasoning: match.confidence_reasoning,
                    semantic_skill_matches: match.semantic_skill_matches,
                    transferable_skills: match.transferable_skills,
                    inferred_strengths: match.inferred_strengths,
                    inferred_gaps: match.inferred_gaps,
                    recommendation: match.recommendation,
                    category_scores: match.category_scores,
                    confidence_score: match.confidence_score ?? undefined,
                    matched_skills: match.matched_skills,
                    missing_skills: match.missing_skills,
                    evaluated_at: match.evaluated_at ?? undefined,
                  }}
                />
              ))
            )}
          </div>
        </div>

        {/* ATS Candidate Insights */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Brain className="w-4 h-4 text-[#FF5A1F]" /> ATS Candidate Insights
            </h2>
          </div>
          <div className="p-6 space-y-3 text-sm">
            {candidate.parse_status === "failed" ? (
              <p className="text-amber-800">
                Resume parsing failed
                {candidate.parse_error ? `: ${candidate.parse_error}` : ""}. Re-upload the resume or contact support.
              </p>
            ) : candidate.parse_status && candidate.parse_status !== "completed" ? (
              <p className="text-slate-500">Resume parsing in progress…</p>
            ) : null}
            {(() => {
              const pr = candidate.parsed_resume_data;
              const skillsLine = pr?.skills?.length ? pr.skills.join(", ") : null;
              const inferredLine = pr?.inferred_skills?.length ? pr.inferred_skills.join(", ") : null;
              const ecosystemLine = pr?.ecosystem_tags?.length ? pr.ecosystem_tags.join(", ") : null;
              return (
                <>
                  <p>
                    <span className="font-medium">Extracted Skills:</span>{" "}
                    {skillsLine ?? "Not extracted from resume yet — re-upload or wait for parse to finish."}
                  </p>
                  {inferredLine ? (
                    <p>
                      <span className="font-medium">Inferred skills (AI):</span> {inferredLine}
                    </p>
                  ) : null}
                  {ecosystemLine ? (
                    <p>
                      <span className="font-medium">Ecosystem tags:</span> {ecosystemLine}
                    </p>
                  ) : null}
                  {pr?.seniority_guess ? (
                    <p>
                      <span className="font-medium">Seniority (estimate):</span> {pr.seniority_guess}
                    </p>
                  ) : null}
                  {(pr?.cloud_platforms?.length ?? 0) > 0 ? (
                    <p>
                      <span className="font-medium">Cloud / platforms:</span> {(pr?.cloud_platforms ?? []).join(", ")}
                    </p>
                  ) : null}
                  {pr?.resume_recruiter_summary ? (
                    <p className="rounded-md border border-slate-100 bg-slate-50/80 p-2 text-slate-700">
                      <span className="font-medium">Resume summary:</span> {pr.resume_recruiter_summary}
                    </p>
                  ) : null}
                </>
              );
            })()}
            <p><span className="font-medium">Extracted Experience:</span> {candidate.parsed_resume_data?.years_of_experience ?? candidate.years_experience ?? "-"}</p>
            <p><span className="font-medium">Parsed Titles:</span> {candidate.parsed_resume_data?.previous_titles?.length ? candidate.parsed_resume_data.previous_titles.join(", ") : "-"}</p>
            <p><span className="font-medium">Parsed Education:</span> {Array.isArray(candidate.parsed_resume_data?.education) ? candidate.parsed_resume_data?.education.join(", ") : (candidate.parsed_resume_data?.education ?? candidate.education ?? "-")}</p>
            <p><span className="font-medium">Certifications:</span> {candidate.parsed_resume_data?.certifications?.length ? candidate.parsed_resume_data.certifications.join(", ") : "-"}</p>
          </div>
        </div>
      </div>

      {/* Right Column: Timeline & Interviews */}
      <div className="space-y-6">

        {/* Interviews */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#FF5A1F]" /> Interviews
            </h2>
          </div>
          <div className="p-5 space-y-5">
            {/* Schedule New */}
            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100 space-y-3">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Schedule New</h3>
              <div className="space-y-2">
                <Input type="datetime-local" className="text-sm h-9" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
                <Input placeholder="Interviewer Name" className="text-sm h-9" value={interviewerName} onChange={(e) => setInterviewerName(e.target.value)} />
                <div className="flex gap-2">
                  <select
                    className="flex-1 rounded-md border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-[#FF5A1F]"
                    value={interviewType}
                    onChange={(e) => setInterviewType(e.target.value as "HR" | "TECH")}
                  >
                    <option value="HR">HR</option>
                    <option value="TECH">Technical</option>
                  </select>
                  <Button onClick={handleScheduleInterview} size="sm" className="bg-slate-900 hover:bg-slate-800 text-white">
                    <Plus className="w-4 h-4 mr-1" /> Add
                  </Button>
                </div>
              </div>
            </div>
  {/* List */}
  <div className="space-y-3">
    {interviews.length === 0 ? (
      <p className="text-sm text-center text-gray-500 py-4">No upcoming interviews.</p>
    ) : (
      interviews.map((interview) => (
        <div key={interview.id} className="relative rounded-xl border border-gray-200 p-4 hover:border-[#FF5A1F]/30 transition-colors">
          <div className="absolute top-4 right-4">
            <span className={cn(
              "px-2 py-1 text-[10px] font-bold uppercase rounded-md tracking-wider",
              interview.status === "scheduled" ? "bg-blue-100 text-blue-700" :
                interview.status === "completed" ? "bg-green-100 text-green-700" :
                  interview.status === "cancelled" ? "bg-red-100 text-red-700" :
                    "bg-gray-100 text-gray-700"
            )}>
              {interview.status}
            </span>
          </div>
          <p className="font-semibold text-gray-900 text-sm pr-16">{interview.interviewer_name ?? "Interviewer TBD"}</p>

          <div className="mt-2 space-y-1 text-xs text-gray-600">
            <p className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-gray-400" /> {new Date(interview.scheduled_at).toLocaleString()}</p>
            <p className="flex items-center gap-1.5"><Briefcase className="w-3.5 h-3.5 text-gray-400" /> Type: {interviewMetaById.get(interview.id)?.interview_type ?? "HR"}</p>
            <p className="flex items-center gap-1.5"><Star className="w-3.5 h-3.5 text-gray-400" /> Rating: {interviewMetaById.get(interview.id)?.rating ?? "-"}/5</p>
          </div>

          {interview.status !== "completed" && interview.status !== "cancelled" && (
            <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
              <div className="flex gap-2">
                <Input
                  type="datetime-local"
                  className="text-xs h-8"
                  value={rescheduleTimes[interview.id] ?? ""}
                  onChange={(e) => setRescheduleTimes((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                />
                <Button
                  variant="outline" size="sm" className="h-8 text-xs px-2"
                  onClick={() => handleReschedule(interview.id)}
                  disabled={interviewUpdatingId === interview.id || !rescheduleTimes[interview.id]}
                >
                  Reschedule
                </Button>
              </div>

              <div className="flex gap-2">
                <Input
                  placeholder="Feedback..."
                  className="text-xs h-8 flex-1"
                  value={feedbackNotes[interview.id] ?? ""}
                  onChange={(e) => setFeedbackNotes((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                />
                <select
                  className="w-16 rounded-md border border-gray-200 px-1 py-1 text-xs outline-none"
                  value={feedbackRatings[interview.id] ?? ""}
                  onChange={(e) => setFeedbackRatings((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                >
                  <option value="">Rtg</option>
                  {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
                <Button
                  size="sm" className="h-8 text-xs px-2 bg-green-600 hover:bg-green-700 text-white"
                  onClick={() => handleSaveFeedback(interview.id)}
                  disabled={interviewUpdatingId === interview.id}
                >
                  Complete
                </Button>
              </div>
              <Button
                variant="ghost" size="sm" className="w-full h-8 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={() => handleCancelInterview(interview.id)}
                disabled={interviewUpdatingId === interview.id || interview.status === "cancelled"}
              >
                Cancel Interview
              </Button>
            </div>
          )}
        </div>
      ))
    )}
              </div>
            </div>
          </div>

        {/* Record Details */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#FF5A1F]" /> Record Details
            </h2>
          </div>
          <div className="p-5 space-y-4">
            <div className="flex flex-col gap-1 pb-3 border-b border-gray-100">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Created On</span>
              <span className="text-sm font-semibold text-gray-900">
                {candidate.created_at ? new Date(candidate.created_at).toLocaleDateString() : "Unknown"}
              </span>
            </div>
            <div className="flex flex-col gap-1 pb-3 border-b border-gray-100">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Source</span>
              <span className="text-sm font-semibold text-gray-900 capitalize">
                {candidate.source ? candidate.source.replace('_', ' ') : "Direct"}
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Last Updated</span>
              <span className="text-sm font-semibold text-gray-900">
                {candidate.updated_at ? new Date(candidate.updated_at).toLocaleDateString() : "Unknown"}
              </span>
            </div>
          </div>
        </div>

  {/* Timeline / Interactions */ }
  <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
    <div className="border-b border-gray-100 bg-gray-50/50 p-5">
      <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-[#FF5A1F]" /> Activity Timeline
      </h2>
    </div>
    <div className="p-5">
      <div className="flex gap-2 mb-6 relative">
        <Input placeholder="Add a note..." className="pr-20" value={newNote} onChange={(e) => setNewNote(e.target.value)} />
        <Button size="sm" className="absolute right-1 top-1 bottom-1 h-auto bg-[#FF5A1F] hover:bg-[#E54E1A] text-white" onClick={handleAddNote} disabled={addingNote || !newNote.trim()}>
          {addingNote ? "..." : "Post"}
        </Button>
      </div>

      <div className="space-y-4 relative before:absolute before:inset-0 before:ml-4 before:-translate-x-px before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-200 before:to-transparent">
        {interactionsLoadFailed ? (
          <p className="text-amber-700 text-center py-4 relative z-10 bg-white">Unable to load interactions. You can still view the profile and ATS data.</p>
        ) : orderedTimeline.length === 0 ? (
          <p className="text-sm text-center text-gray-500 py-4 relative z-10 bg-white">No activity yet.</p>
        ) : (
          orderedTimeline.map((item) => (
            <div key={item.id} className="relative z-10 pl-10">
              {/* Timeline dot */}
              <div className="absolute left-[6px] top-1.5 h-5 w-5 rounded-full border-4 border-white bg-[#FF5A1F] shadow-sm"></div>

              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 shadow-sm transition-transform hover:-translate-y-0.5">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="font-semibold text-gray-900 text-sm">{item.title ?? item.interaction_type}</p>
                  <span className="text-[10px] font-medium text-gray-400 whitespace-nowrap">{new Date(item.created_at).toLocaleDateString()}</span>
                </div>
                {item.body && <p className="text-xs text-gray-600 leading-relaxed">{item.body}</p>}
                {item.metadata && (
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-gray-100 p-2.5 text-[10px] text-gray-700 font-mono border border-gray-200">
                    {JSON.stringify(item.metadata, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  </div>

        </div >
      </div >
    </section >
  );
}
