"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, API_BASE_URL } from "@/lib/api/client";
import {
  addCandidateInteraction,
  createCommunicationTemplate,
  createCandidateCommunicationReminder,
  duplicateCommunicationTemplate,
  assignCandidateRecruiter,
  createCandidateInterview,
  disconnectCommunicationProvider,
  getCandidateCommunicationMessages,
  getCandidateCommunicationReminders,
  getCandidateById,
  getCandidateInteractions,
  getCandidateInterviews,
  getCommunicationConnections,
  getCommunicationTemplates,
  renderCommunicationTemplate,
  runDueCommunicationReminders,
  sendCandidateEmail,
  sendCandidateWhatsApp,
  startCommunicationOAuth,
  updateCandidate,
  updateCandidateInterview,
  updateCommunicationTemplate,
  type CandidateInteraction,
  type CommunicationConnection,
  type CommunicationMessage,
  type CommunicationReminder,
  type CommunicationTemplate,
  type InterviewRecord,
} from "@/lib/api/candidates";
import { getInterviews } from "@/lib/api/interviews";
import { InterviewList } from "@/components/interviews/InterviewList";
import { InterviewTimeline } from "@/components/interviews/InterviewTimeline";
import { ScheduleInterviewModal } from "@/components/interviews/ScheduleInterviewModal";
import { getJobs, submitCandidateToJob } from "@/lib/api/jobs";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import {
  atsAwaitingSemanticEnrichment,
  getCandidateMatchesAts,
  pollAtsPairStatusesUntilSettled,
  pollCandidateMatchesUntilEnriched,
  rescoreCandidateAts,
} from "@/lib/api/ats";
import type { Candidate, CandidateMatchEntry, Interview, Job, OrganizationUser, Pipeline } from "@/lib/api/types";
import { getUsers } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Mail, Phone, MapPin, Briefcase, Calendar, FileText, Download, ExternalLink, MessageSquare, Clock, ArrowLeft, Edit3, Save, X, Plus, User, Star, Sparkles, Layers , Activity, Brain, CornerDownLeft, Paperclip, Bold, Italic, Underline, List as ListIcon, ListOrdered, Link as LinkIcon, Search, ChevronDown, Maximize2, MoreVertical, ChevronLeft, ChevronRight, Copy, Filter, Image as ImageIcon, MoreHorizontal, CheckCircle2, Eye } from "lucide-react";
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
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [schedulingModalOpen, setSchedulingModalOpen] = useState(false);
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [composeEmailTo, setComposeEmailTo] = useState("");
  const [phone, setPhone] = useState("");
  const [composePhoneTo, setComposePhoneTo] = useState("");
  const [location, setLocation] = useState("");
  const [role, setRole] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [newNote, setNewNote] = useState("");
  const [selectedRecruiterId, setSelectedRecruiterId] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [submitJobId, setSubmitJobId] = useState("");
  const [submittingToJob, setSubmittingToJob] = useState(false);
  const [updatingPipelineId, setUpdatingPipelineId] = useState<string | null>(null);
  const [atsMatches, setAtsMatches] = useState<CandidateMatchEntry[]>([]);
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsRescoreBusy, setAtsRescoreBusy] = useState(false);
  const [atsHint, setAtsHint] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("profile");
  const [activeCommunicationTab, setActiveCommunicationTab] = useState<"timeline" | "email" | "whatsapp" | "templates">("timeline");
  const [communicationConnections, setCommunicationConnections] = useState<CommunicationConnection[]>([]);
  const [communicationTemplates, setCommunicationTemplates] = useState<CommunicationTemplate[]>([]);
  const [communicationMessages, setCommunicationMessages] = useState<CommunicationMessage[]>([]);
  const [communicationReminders, setCommunicationReminders] = useState<CommunicationReminder[]>([]);
  const [communicationLoading, setCommunicationLoading] = useState(false);
  const [communicationError, setCommunicationError] = useState<string | null>(null);
  const [timelineChannelFilter, setTimelineChannelFilter] = useState<"all" | "email" | "whatsapp">("all");
  const [timelineStatusFilter, setTimelineStatusFilter] = useState<"all" | "draft" | "queued" | "sent" | "delivered" | "read" | "replied" | "failed">("all");
  const [selectedEmailProvider, setSelectedEmailProvider] = useState<"gmail" | "outlook">("gmail");
  const [selectedWhatsappTemplateId, setSelectedWhatsappTemplateId] = useState("");
  const [whatsappBody, setWhatsappBody] = useState("");
  const [sendingWhatsapp, setSendingWhatsapp] = useState(false);
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [templateSearch, setTemplateSearch] = useState("");
  const [emailSearch, setEmailSearch] = useState("");
  const [whatsappSearch, setWhatsappSearch] = useState("");
  const [templateCategoryFilter, setTemplateCategoryFilter] = useState<string>("all");
  const [templateValuesInput, setTemplateValuesInput] = useState("");
  const [templatePreview, setTemplatePreview] = useState<string>("");
  const [emailTemplateRendering, setEmailTemplateRendering] = useState(false);
  const [whatsappTemplateRendering, setWhatsappTemplateRendering] = useState(false);
  const [schedulingReminder, setSchedulingReminder] = useState(false);
  const [attachments, setAttachments] = useState<Array<{ filename: string; content_type: string; content_base64: string }>>([]);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateCategory, setNewTemplateCategory] = useState("email");
  const [newTemplateSubject, setNewTemplateSubject] = useState("");
  const [newTemplateBody, setNewTemplateBody] = useState("");
  const [reminderChannel, setReminderChannel] = useState<"email" | "whatsapp">("email");
  const [reminderAt, setReminderAt] = useState("");
  const [runningReminders, setRunningReminders] = useState(false);
  const [communicationNotice, setCommunicationNotice] = useState<string | null>(null);
  const [isEditingTemplate, setIsEditingTemplate] = useState(false);
  const candidateLoadSeqRef = useRef(0);
  const templateEditorRef = useRef<HTMLTextAreaElement>(null);
  const atsSemanticInFlight = useMemo(() => atsAwaitingSemanticEnrichment(atsMatches), [atsMatches]);

  const insertVariable = (variable: string) => {
    if (selectedTemplateId) return;
    const textarea = templateEditorRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = newTemplateBody;
    const before = text.substring(0, start);
    const after = text.substring(end);
    
    setNewTemplateBody(before + variable + after);
    
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + variable.length, start + variable.length);
    }, 0);
  };

  const handleEditExistingTemplate = () => {
    const tpl = communicationTemplates.find(t => t.id === selectedTemplateId);
    if (!tpl) return;
    setNewTemplateName(tpl.name);
    setNewTemplateCategory(tpl.channel);
    setNewTemplateSubject(tpl.subject_template || "");
    setNewTemplateBody(tpl.body_template);
    setIsEditingTemplate(true);
  };

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
        // Fire candidate + all supporting data concurrently; none depends on another.
        const [data, timelineResult, pipelinesResult, interviewResult, jobsResult, usersResult] =
          await Promise.all([
            getCandidateById(params.candidateId),
            getCandidateInteractions(params.candidateId, 100, 0).catch(() => null),
            getPipelines(200, 0, undefined, params.candidateId).catch(() => []),
            getInterviews({ candidate_id: params.candidateId, limit: 100 }).catch(() => []),
            getJobs(50, 0).catch(() => []),
            getUsers().catch(() => []),
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
        setInteractionsLoadFailed(timelineResult === null);
        setInteractions(timelineResult ?? []);
        const loadedPipelines = pipelinesResult as Pipeline[];
        setPipelines(loadedPipelines);
        setInterviews(interviewResult as Interview[]);
        setJobs((jobsResult as Job[]).filter(Boolean));
        setUsers((usersResult as OrganizationUser[]).filter((u) => u.role === "recruiter" || u.role === "admin"));
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
        setFirstName(data.first_name || "");
        setLastName(data.last_name || "");
        setEmail(data.email || "");
        setComposeEmailTo(data.email || "");
        setPhone(data.phone ?? "");
        setComposePhoneTo(data.phone ?? "");
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


  const loadCommunicationTemplates = useCallback(async () => {
    const query = templateSearch || undefined;
    const [emailTemplates, whatsappTemplates] = await Promise.all([
      getCommunicationTemplates("email", { search: query }),
      getCommunicationTemplates("whatsapp", { search: query }),
    ]);
    const deduped = new Map<string, CommunicationTemplate>();
    for (const tpl of [...emailTemplates, ...whatsappTemplates]) {
      if (!tpl.is_deleted) {
        deduped.set(tpl.id, tpl);
      }
    }
    return Array.from(deduped.values()).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  }, [templateSearch]);

  useEffect(() => {
    if (!params.candidateId || activeTab !== "communication") return;
    async function loadCommunicationData() {
      setCommunicationLoading(true);
      setCommunicationError(null);
      try {
        const [connections, templates, messages, reminders] = await Promise.all([
          getCommunicationConnections(),
          loadCommunicationTemplates(),
          getCandidateCommunicationMessages(params.candidateId, 50),
          getCandidateCommunicationReminders(params.candidateId),
        ]);
        setCommunicationConnections(connections);
        setCommunicationTemplates(templates);
        setCommunicationMessages(messages);
        setCommunicationReminders(reminders);
      } catch (err) {
        setCommunicationError(err instanceof Error ? err.message : "Unable to load communication data.");
      } finally {
        setCommunicationLoading(false);
      }
    }
    void loadCommunicationData();
  }, [activeTab, params.candidateId, loadCommunicationTemplates]);

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

  const unifiedTimelineEvents = useMemo(() => {
    type UnifiedEvent = {
      id: string;
      type: "email" | "whatsapp" | "interview" | "note" | "status_change" | "call" | "reply" | "profile";
      title: string;
      subtitle?: string;
      content?: string;
      status?: string;
      timestamp: Date;
      metadata?: any;
    };
    const events: UnifiedEvent[] = [];

    // Add communication messages
    for (const msg of communicationMessages) {
      if (timelineChannelFilter !== "all" && msg.channel !== timelineChannelFilter) continue;
      if (timelineStatusFilter !== "all" && msg.status !== timelineStatusFilter) continue;
      
      const isReply = (msg.status as string) === "replied";
      events.push({
        id: `msg-${msg.id}`,
        type: isReply ? "reply" : (msg.channel === "whatsapp" ? "whatsapp" : "email"),
        title: isReply ? `Candidate replied to ${msg.channel}` : `${msg.channel === "whatsapp" ? "WhatsApp message" : "Email"} ${(msg.status as string) === "draft" ? "drafted" : "sent"}`,
        subtitle: isReply ? (msg.subject ? `Re: ${msg.subject}` : undefined) : (msg.channel === "whatsapp" ? (msg.body || undefined) : (msg.subject ? `Subject: ${msg.subject}` : undefined)),
        content: isReply ? undefined : (msg.channel === "email" ? `To: ${msg.to_address || candidate?.email}` : undefined),
        status: msg.status,
        timestamp: new Date(msg.created_at),
        metadata: msg,
      });
    }

    // Add interactions
    for (const inter of interactions) {
      if (timelineChannelFilter !== "all") continue; // if filtered to email/whatsapp, hide other interactions
      
      let type: UnifiedEvent["type"] = inter.interaction_type === "note" ? "note" : inter.interaction_type === "interview" ? "interview" : (inter.interaction_type as string) === "call" ? "call" : (inter.interaction_type as string) === "status_change" ? "status_change" : "profile";
      
      if (inter.title?.toLowerCase().includes("profile added") || (inter.interaction_type as any) === "profile") type = "profile";

      let subtitle = inter.body;
      let content = undefined;

      if (type === "interview") {
        const d = inter.metadata?.scheduled_at ? new Date(inter.metadata.scheduled_at as string) : null;
        if (d) {
           content = d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }) + ", " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
        }
        if (inter.metadata?.interview_type) {
           subtitle = `${inter.metadata.interview_type} Round`;
        }
      }

      events.push({
        id: `inter-${inter.id}`,
        type,
        title: inter.title || "",
        subtitle: subtitle || undefined,
        content: content || undefined,
        timestamp: new Date(inter.created_at),
        metadata: inter,
      });
    }

    events.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    return events;
  }, [communicationMessages, interactions, timelineChannelFilter, timelineStatusFilter, candidate?.email]);

  const groupedUnifiedTimeline = useMemo(() => {
    return unifiedTimelineEvents.reduce<Record<string, typeof unifiedTimelineEvents>>((acc, event) => {
      const d = event.timestamp;
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      
      let key = "";
      if (d.toDateString() === today.toDateString()) {
        key = "Today";
      } else if (d.toDateString() === yesterday.toDateString()) {
        key = "Yesterday";
      } else {
        key = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      }

      acc[key] = acc[key] || [];
      acc[key].push(event);
      return acc;
    }, {});
  }, [unifiedTimelineEvents]);

  const communicationSummary = useMemo(() => {
    const total = communicationMessages.length;
    const emails = communicationMessages.filter((m) => m.channel === "email").length;
    const whatsapp = communicationMessages.filter((m) => m.channel === "whatsapp").length;
    const replies = communicationMessages.filter((m) => (m.status as string) === "replied").length;
    return { total, emails, whatsapp, replies };
  }, [communicationMessages]);

  useEffect(() => {
    if (!communicationNotice) return;
    const t = setTimeout(() => setCommunicationNotice(null), 2600);
    return () => clearTimeout(t);
  }, [communicationNotice]);

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
  const eligiblePipelines = useMemo(
    () => pipelines.filter((p) => ["screening", "interview", "offer", "placed"].includes(p.stage)),
    [pipelines]
  );
  const recruiterName = users.find((user) => user.id === candidate?.recruiter_id)?.email ?? candidate?.recruiter_id ?? "-";
  const candidateJobId = currentPipeline?.job_id ?? null;
  const jobTitle = jobs.find((job) => job.id === candidateJobId)?.title ?? (candidateJobId || "-");
  const templateMergeValues = useMemo(() => {
    const nextInterview = [...interviews]
      .filter((item) => item.status === "scheduled")
      .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0];
    const interviewDate = nextInterview ? new Date(nextInterview.scheduled_at) : null;
    const candidateName = `${candidate?.first_name || ""} ${candidate?.last_name || ""}`.trim();
    return {
      candidate_name: candidateName || "Candidate",
      job_title: jobTitle && jobTitle !== "-" ? jobTitle : candidate?.role || "Role",
      company_name: "AIRIS",
      interview_date: interviewDate
        ? interviewDate.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
        : "Interview date",
      interview_time: interviewDate
        ? interviewDate.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
        : "Interview time",
      interview_mode: "Video Call",
    };
  }, [candidate?.first_name, candidate?.last_name, candidate?.role, interviews, jobTitle]);
  const parseTemplateValues = useCallback((): Record<string, unknown> | null => {
    if (!templateValuesInput.trim()) {
      return { ...templateMergeValues };
    }
    try {
      const parsed = JSON.parse(templateValuesInput) as Record<string, unknown>;
      return { ...templateMergeValues, ...parsed };
    } catch {
      setCommunicationError("Template values must be valid JSON before sending or scheduling.");
      return null;
    }
  }, [templateMergeValues, templateValuesInput]);

  const fillEmailFromTemplate = useCallback(async (templateId: string) => {
    setEmailTemplateRendering(true);
    setCommunicationError(null);
    try {
      const rendered = await renderCommunicationTemplate(templateId, templateMergeValues);
      setSelectedWhatsappTemplateId("");
      setEmailSubject(rendered.subject || "");
      setEmailBody(rendered.body);
      setTemplatePreview(rendered.body);
      if (rendered.unresolved_placeholders.length > 0) {
        setCommunicationNotice(`Template loaded. Missing values: ${rendered.unresolved_placeholders.join(", ")}.`);
      }
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to load selected email template.");
    } finally {
      setEmailTemplateRendering(false);
    }
  }, [templateMergeValues]);

  const fillWhatsAppFromTemplate = useCallback(async (templateId: string) => {
    setWhatsappTemplateRendering(true);
    setCommunicationError(null);
    try {
      const rendered = await renderCommunicationTemplate(templateId, templateMergeValues);
      setSelectedTemplateId("");
      setWhatsappBody(rendered.body);
      setTemplatePreview(rendered.body);
      if (rendered.unresolved_placeholders.length > 0) {
        setCommunicationNotice(`Template loaded. Missing values: ${rendered.unresolved_placeholders.join(", ")}.`);
      }
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to load selected WhatsApp template.");
    } finally {
      setWhatsappTemplateRendering(false);
    }
  }, [templateMergeValues]);

  useEffect(() => {
    if (!selectedTemplateId || activeCommunicationTab === "templates") return;
    const template = communicationTemplates.find((tpl) => tpl.id === selectedTemplateId);
    if (!template || template.channel !== "email") return;
    void fillEmailFromTemplate(selectedTemplateId);
  }, [activeCommunicationTab, communicationTemplates, fillEmailFromTemplate, selectedTemplateId]);

  useEffect(() => {
    if (!selectedWhatsappTemplateId || activeCommunicationTab === "templates") return;
    const template = communicationTemplates.find((tpl) => tpl.id === selectedWhatsappTemplateId);
    if (!template || (template.channel !== "whatsapp" && !template.name.toLowerCase().includes("whatsapp"))) return;
    void fillWhatsAppFromTemplate(selectedWhatsappTemplateId);
  }, [activeCommunicationTab, communicationTemplates, fillWhatsAppFromTemplate, selectedWhatsappTemplateId]);

  useEffect(() => {
    const connectedProviders = new Set(
      communicationConnections.filter((conn) => conn.status === "connected").map((conn) => conn.provider)
    );
    if (connectedProviders.has("gmail")) {
      setSelectedEmailProvider("gmail");
    } else if (connectedProviders.has("outlook")) {
      setSelectedEmailProvider("outlook");
    }
  }, [communicationConnections]);

  function previewTemplateText(raw: string) {
    return raw.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key: string) => {
      const value = templateMergeValues[key as keyof typeof templateMergeValues];
      return value === undefined || value === null || value === "" ? match : String(value);
    });
  }

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
      setComposeEmailTo(updated.email || "");
      setComposePhoneTo(updated.phone || "");
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

  async function refreshInterviewData() {
    if (!params.candidateId) return;
    const [timeline, interviewList] = await Promise.all([
      getCandidateInteractions(params.candidateId, 100, 0),
      getInterviews({ candidate_id: params.candidateId, limit: 100 }).catch(() => [] as Interview[]),
    ]);
    setInteractions(timeline);
    setInterviews(interviewList);
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

  async function refreshCommunicationPanel() {
    if (!params.candidateId) return;
    const [connections, templates, messages, reminders] = await Promise.all([
      getCommunicationConnections(),
      loadCommunicationTemplates(),
      getCandidateCommunicationMessages(params.candidateId, 50),
      getCandidateCommunicationReminders(params.candidateId),
    ]);
    setCommunicationConnections(connections);
    setCommunicationTemplates(templates);
    setCommunicationMessages(messages);
    setCommunicationReminders(reminders);
  }

  async function handleConnectProvider(provider: "gmail" | "outlook") {
    try {
      const oauth = await startCommunicationOAuth(provider);
      window.open(oauth.authorization_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : `Unable to connect ${provider}.`);
    }
  }

  async function handleDisconnectProvider(provider: "gmail" | "outlook") {
    try {
      await disconnectCommunicationProvider(provider);
      await refreshCommunicationPanel();
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : `Unable to disconnect ${provider}.`);
    }
  }

  async function handleSendEmail(saveAsDraft = false, quickAction?: string) {
    if (!params.candidateId || !composeEmailTo) return;
    setSendingEmail(true);
    setCommunicationError(null);
    try {
      if (selectedTemplateId && parseTemplateValues() === null) return;
      const payload = {
        provider: selectedEmailProvider,
        to_email: composeEmailTo,
        subject: emailSubject,
        body: emailBody,
        save_as_draft: saveAsDraft,
        quick_action: quickAction,
        attachments,
        idempotency_key: `${params.candidateId}-${Date.now()}`,
      };
      await sendCandidateEmail(params.candidateId, payload);
      setEmailSubject("");
      setEmailBody("");
      setSelectedTemplateId("");
      setTemplateValuesInput("");
      setTemplatePreview("");
      setAttachments([]);
      await refreshCommunicationPanel();
      await refreshInterviewData();
      setCommunicationNotice(saveAsDraft ? "Draft saved." : "Email sent successfully.");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to send email.");
    } finally {
      setSendingEmail(false);
    }
  }

  async function handleSendWhatsApp(quickAction?: string) {
    if (!params.candidateId || !composePhoneTo) return;
    setSendingWhatsapp(true);
    setCommunicationError(null);
    try {
      if (selectedWhatsappTemplateId && parseTemplateValues() === null) return;
      await sendCandidateWhatsApp(params.candidateId, {
        to_phone: composePhoneTo,
        body: whatsappBody || undefined,
        idempotency_key: `${params.candidateId}-wa-${Date.now()}`,
        quick_action: quickAction,
      });
      setWhatsappBody("");
      setSelectedWhatsappTemplateId("");
      setTemplateValuesInput("");
      await refreshCommunicationPanel();
      setCommunicationNotice("WhatsApp message sent.");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to send WhatsApp message.");
    } finally {
      setSendingWhatsapp(false);
    }
  }

  async function handleCreateReminder() {
    if (!params.candidateId || !reminderAt || !candidate) return;
    setSchedulingReminder(true);
    setCommunicationError(null);
    try {
      const parsedValues = parseTemplateValues();
      if (parsedValues === null) return;
      const templateId = reminderChannel === "email" ? selectedTemplateId : selectedWhatsappTemplateId;
      await createCandidateCommunicationReminder(params.candidateId, {
        channel: reminderChannel,
        provider: reminderChannel === "email" ? selectedEmailProvider : "whatsapp",
        to_address: reminderChannel === "email" ? (composeEmailTo || "") : (composePhoneTo || ""),
        template_id: templateId || undefined,
        template_values: parsedValues,
        subject: reminderChannel === "email" ? (emailSubject || undefined) : undefined,
        body: reminderChannel === "email" ? (emailBody || undefined) : (whatsappBody || undefined),
        scheduled_for: new Date(reminderAt).toISOString(),
      });
      setReminderAt("");
      await refreshCommunicationPanel();
      setCommunicationNotice("Reminder scheduled.");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to schedule reminder.");
    } finally {
      setSchedulingReminder(false);
    }
  }

  async function handleRunDueReminders() {
    setRunningReminders(true);
    try {
      await runDueCommunicationReminders();
      await refreshCommunicationPanel();
      setCommunicationNotice("Due reminders processed.");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to process reminders.");
    } finally {
      setRunningReminders(false);
    }
  }

  async function handleDuplicateTemplate(templateId: string) {
    try {
      await duplicateCommunicationTemplate(templateId);
      await refreshCommunicationPanel();
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to duplicate template.");
    }
  }

  async function handleAttachmentSelected(file: File | null) {
    if (!file) return;
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Failed to read attachment"));
      reader.readAsDataURL(file);
    });
    const contentBase64 = dataUrl.includes(",") ? dataUrl.split(",")[1] : dataUrl;
    setAttachments((prev) => [
      ...prev,
      { filename: file.name, content_type: file.type || "application/octet-stream", content_base64: contentBase64 },
    ]);
  }

  async function handleSaveTemplate() {
    if (!newTemplateName.trim() || !newTemplateBody.trim()) return;
    setCreatingTemplate(true);
    setCommunicationError(null);
    try {
      if (isEditingTemplate && selectedTemplateId) {
        await updateCommunicationTemplate(selectedTemplateId, {
          name: newTemplateName.trim(),
          subject_template: newTemplateCategory === "whatsapp" ? undefined : (newTemplateSubject.trim() || undefined),
          body_template: newTemplateBody,
        });
      } else {
        await createCommunicationTemplate({
          channel: newTemplateCategory as "email" | "whatsapp",
          name: newTemplateName.trim(),
          subject_template: newTemplateCategory === "whatsapp" ? undefined : (newTemplateSubject.trim() || undefined),
          body_template: newTemplateBody,
        });
      }
      setNewTemplateName("");
      setNewTemplateCategory("email");
      setNewTemplateSubject("");
      setNewTemplateBody("");
      setIsEditingTemplate(false);
      setSelectedTemplateId("");
      await refreshCommunicationPanel();
      setActiveCommunicationTab("templates");
    } catch (err) {
      setCommunicationError(err instanceof Error ? err.message : "Unable to save template.");
    } finally {
      setCreatingTemplate(false);
    }
  }

  function handleUseSelectedTemplate() {
    const tpl = communicationTemplates.find((item) => item.id === selectedTemplateId);
    if (!tpl) {
      setCommunicationError("Select a template before using it.");
      return;
    }
    if (tpl.channel === "whatsapp" || tpl.name.toLowerCase().includes("whatsapp")) {
      setSelectedWhatsappTemplateId(tpl.id);
      setActiveCommunicationTab("whatsapp");
      return;
    }
    setSelectedTemplateId(tpl.id);
    setActiveCommunicationTab("email");
  }

  const emailTemplates = communicationTemplates.filter((tpl) => tpl.channel === "email");
  const whatsappTemplates = communicationTemplates.filter(
    (tpl) => tpl.channel === "whatsapp" || tpl.name.toLowerCase().includes("whatsapp")
  );
  const emailSendDisabled = sendingEmail || emailTemplateRendering || !composeEmailTo || !emailSubject.trim() || !emailBody.trim();
  const emailDraftDisabled = sendingEmail || emailTemplateRendering || !composeEmailTo || !emailBody.trim();
  const whatsappSendDisabled = sendingWhatsapp || whatsappTemplateRendering || !composePhoneTo || !whatsappBody.trim();
  const reminderDisabled =
    schedulingReminder ||
    !reminderAt ||
    (reminderChannel === "email" ? !composeEmailTo || !emailSubject.trim() || !emailBody.trim() : !composePhoneTo || !whatsappBody.trim());


  return (
    <section className="mx-auto max-w-[1240px] space-y-6 pb-12">
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
      {/* Main Content Area: Tabs */}
      <div className={cn(activeTab === "communication" ? "lg:col-span-3" : "lg:col-span-2", "space-y-6")}>
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab("profile")}
            className={cn(
              "px-6 py-3 text-sm font-semibold transition-colors relative",
              activeTab === "profile" ? "text-[#FF5A1F]" : "text-gray-500 hover:text-gray-700"
            )}
          >
            Profile Details
            {activeTab === "profile" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF5A1F]" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("ats")}
            className={cn(
              "px-6 py-3 text-sm font-semibold transition-colors relative",
              activeTab === "ats" ? "text-[#FF5A1F]" : "text-gray-500 hover:text-gray-700"
            )}
          >
            ATS Insights
            {activeTab === "ats" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF5A1F]" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("communication")}
            className={cn(
              "px-6 py-3 text-sm font-semibold transition-colors relative",
              activeTab === "communication" ? "text-[#FF5A1F]" : "text-gray-500 hover:text-gray-700"
            )}
          >
            Communication Hub
            {activeTab === "communication" && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF5A1F]" />
            )}
          </button>
        </div>

        <div className="transition-all duration-300">
          {activeTab === "profile" && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
              {/* Detailed Profile */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="border-b border-gray-100 bg-gray-50/50 p-5 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                    <User className="w-4 h-4 text-[#FF5A1F]" /> Profile Details
                  </h2>
                  {isEditing ? (
                    <div className="flex items-center gap-2">
                      <Button variant="outline" onClick={handleCancel} disabled={isSaving} className="h-8 text-xs">
                        <X className="w-3 h-3 mr-1" /> Cancel
                      </Button>
                      <Button onClick={handleSave} disabled={isSaving} className="h-8 text-xs bg-[#FF5A1F] hover:bg-[#E54E1A] text-white">
                        <Save className="w-3 h-3 mr-1" /> {isSaving ? "Saving..." : "Save"}
                      </Button>
                    </div>
                  ) : (
                    <Button variant="outline" onClick={() => setIsEditing(true)} className="h-8 text-xs bg-white border-gray-200 hover:bg-gray-50 text-gray-700">
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
            </div>
          )}

          {activeTab === "ats" && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
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
          )}
          {activeTab === "communication" && (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="border-b border-gray-100 bg-gray-50/50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-[#FF5A1F]" />
                      <h2 className="text-base font-semibold text-gray-900">Communication Hub</h2>
                    </div>
                  </div>
                </div>
                <div className="border-b border-gray-100 px-4">
                  <div className="flex gap-4 text-sm">
                    {(["timeline", "email", "whatsapp", "templates"] as const).map((tabKey) => (
                      <button
                        key={tabKey}
                        onClick={() => setActiveCommunicationTab(tabKey)}
                        className={cn(
                          "py-3 font-medium capitalize border-b-2 -mb-px",
                          activeCommunicationTab === tabKey ? "text-[#FF5A1F] border-[#FF5A1F]" : "text-gray-500 border-transparent"
                        )}
                      >
                        {tabKey}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="p-5 space-y-4">
                  {communicationLoading ? (
                    <div className="space-y-2">
                      <div className="h-3 w-40 animate-pulse rounded bg-slate-100" />
                      <div className="h-20 animate-pulse rounded bg-slate-50 border border-slate-100" />
                    </div>
                  ) : communicationError ? (
                    <p className="text-sm text-red-600">{communicationError}</p>
                  ) : activeCommunicationTab === "timeline" ? (
                      <div className="space-y-4">
                        {communicationNotice ? (
                          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                            {communicationNotice}
                          </div>
                        ) : null}
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                          <div className="lg:col-span-4 rounded-xl border border-gray-200 p-4 space-y-3 bg-white">
                            <div className="flex items-center justify-between gap-2">
                              <h3 className="text-sm font-semibold text-gray-900">Communication Timeline</h3>
                              <select className="rounded-md border border-gray-200 px-2 py-1.5 text-xs" value={timelineStatusFilter} onChange={(e) => setTimelineStatusFilter(e.target.value as "all" | "draft" | "queued" | "sent" | "delivered" | "read" | "replied" | "failed")}>
                                <option value="all">All Types</option>
                                <option value="draft">Draft</option>
                                <option value="queued">Queued</option>
                                <option value="sent">Sent</option>
                                <option value="delivered">Delivered</option>
                                <option value="read">Read</option>
                                <option value="replied">Replied</option>
                                <option value="failed">Failed</option>
                              </select>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              <select className="rounded-md border border-gray-200 px-3 py-2 text-sm" value={timelineChannelFilter} onChange={(e) => setTimelineChannelFilter(e.target.value as "all" | "email" | "whatsapp")}>
                                <option value="all">All channels</option>
                                <option value="email">Email</option>
                                <option value="whatsapp">WhatsApp</option>
                              </select>
                              <div className="rounded-md border border-gray-200 px-3 py-2 text-xs text-gray-500">Recent activity</div>
                            </div>
                            <div className="max-h-[520px] overflow-y-auto pr-2 pb-4">
                            {Object.entries(groupedUnifiedTimeline).length === 0 ? (
                              <div className="rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-500 bg-gray-50 text-center">
                                No communication activity yet.
                              </div>
                            ) : Object.entries(groupedUnifiedTimeline).map(([dateKey, items]) => (
                              <div key={dateKey} className="mb-6 last:mb-0">
                                <p className="text-sm font-bold text-gray-900 mb-4">{dateKey}</p>
                                <div className="relative border-l border-gray-200 ml-3 space-y-6">
                                  {items.map((event) => {
                                    let emoji = "✉️";
                                    let dotColor = "border-orange-200 bg-orange-50";
                                    
                                    if (event.type === "whatsapp") {
                                      emoji = "💬";
                                      dotColor = "border-green-200 bg-green-50";
                                    } else if (event.type === "interview") {
                                      emoji = "📅";
                                      dotColor = "border-blue-200 bg-blue-50";
                                    } else if (event.type === "reply") {
                                      emoji = "↩️";
                                      dotColor = "border-purple-200 bg-purple-50";
                                    } else if (event.type === "profile") {
                                      emoji = "👤";
                                      dotColor = "border-gray-200 bg-gray-50";
                                    } else if (event.type === "note" || event.type === "status_change") {
                                      emoji = "📝";
                                      dotColor = "border-gray-200 bg-gray-50";
                                    }
                                    
                                    return (
                                      <div key={event.id} className="relative pl-8">
                                        <div className={cn("absolute -left-[15px] top-0.5 flex h-[30px] w-[30px] items-center justify-center rounded-full ring-4 ring-white border", dotColor)}>
                                          <span className="text-[14px] leading-none">{emoji}</span>
                                        </div>
                                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                                          <div>
                                            <div className="flex items-center gap-2">
                                              <p className="text-sm font-semibold text-gray-900">{event.title}</p>
                                              {event.status && (
                                                <span className={cn(
                                                  "rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium uppercase",
                                                  event.status === "sent" ? "bg-green-100 text-green-700" :
                                                  event.status === "delivered" ? "bg-emerald-100 text-emerald-700" :
                                                  event.status === "replied" ? "bg-blue-100 text-blue-700" :
                                                  event.status === "failed" ? "bg-red-100 text-red-700" :
                                                  "bg-gray-100 text-gray-600"
                                                )}>
                                                  {event.status}
                                                </span>
                                              )}
                                            </div>
                                            {event.subtitle && <p className="text-sm text-gray-600 mt-0.5">{event.subtitle}</p>}
                                            {event.content && <p className="text-sm text-gray-600 mt-0.5">{event.content}</p>}
                                          </div>
                                          <div className="text-xs text-gray-400 font-medium whitespace-nowrap pt-0.5">
                                            {event.timestamp.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                            </div>
                            <Button variant="outline" className="w-full text-xs h-8">
                              Load more
                            </Button>
                          </div>
                          <div className="lg:col-span-5 space-y-4">
                            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                                <div className="flex items-center gap-2">
                                  <Mail className="w-4 h-4 text-[#FF5A1F]" />
                                  <span className="text-sm font-semibold text-gray-900">Compose Email</span>
                                </div>
                              </div>
                              <div className="p-0">
                                <div className="flex items-center border-b border-gray-100 px-4 py-2">
                                  <span className="text-sm text-gray-500 w-12 font-medium">To</span>
                                  <input className="flex-1 text-sm outline-none bg-transparent" value={composeEmailTo} onChange={(e) => setComposeEmailTo(e.target.value)} />
                                </div>
                                <div className="flex items-center border-b border-gray-100 px-4 py-2">
                                  <span className="text-sm text-gray-500 w-12 font-medium">Sub</span>
                                  <input className="flex-1 text-sm outline-none bg-transparent" placeholder="Enter subject..." value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
                                </div>
                                <div className="flex items-center border-b border-gray-100 px-4 py-2 bg-gray-50/30">
                                   <span className="text-sm text-gray-500 w-[100px] font-medium">Use template</span>
                                   <select className="flex-1 text-sm outline-none bg-transparent text-gray-700 font-medium" value={selectedTemplateId} onChange={(e) => setSelectedTemplateId(e.target.value)}>
                                      <option value="">Select a template (optional)</option>
                                      {emailTemplates.map((tpl) => (
                                        <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                                      ))}
                                   </select>
                                </div>
                                {emailTemplateRendering && (
                                  <p className="px-4 py-1 text-xs font-medium text-[#FF5A1F]">Loading template content...</p>
                                )}
                                <div className="flex items-center gap-1 border-b border-gray-100 px-4 py-1.5 bg-gray-50/50">
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Bold"><Bold className="w-3.5 h-3.5" /></button>
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Italic"><Italic className="w-3.5 h-3.5" /></button>
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Underline"><Underline className="w-3.5 h-3.5" /></button>
                                  <div className="w-px h-4 bg-gray-300 mx-1" />
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Bullet List"><ListIcon className="w-3.5 h-3.5" /></button>
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Numbered List"><ListOrdered className="w-3.5 h-3.5" /></button>
                                  <div className="w-px h-4 bg-gray-300 mx-1" />
                                  <button className="p-1.5 rounded hover:bg-gray-200 text-gray-500 transition-colors" title="Link"><LinkIcon className="w-3.5 h-3.5" /></button>
                                </div>
                                <div className="p-4">
                                  <textarea className="w-full min-h-[170px] text-sm outline-none resize-none bg-transparent" placeholder="Type your message here..." value={emailBody} onChange={(e) => setEmailBody(e.target.value)} />
                                </div>
                              </div>
                              <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                                 <button className="text-gray-500 hover:text-gray-700 transition-colors flex items-center gap-1 text-xs font-medium">
                                   <Paperclip className="w-4 h-4" /> Attach File
                                 </button>
                                 <div className="flex items-center gap-2">
                                    <Button variant="ghost" className="h-8 text-xs text-gray-600 hover:bg-gray-200" onClick={() => void handleSendEmail(true, "timeline_draft")} disabled={emailDraftDisabled}>Save Draft</Button>
                                    <Button className="h-8 text-xs bg-[#FF5A1F] hover:bg-[#E54E1A] text-white shadow-sm px-4" onClick={() => void handleSendEmail(false, "timeline_send")} disabled={emailSendDisabled}>{sendingEmail ? "Sending..." : "Send Email"}</Button>
                                 </div>
                              </div>
                            </div>
                            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                                <div className="flex items-center gap-2">
                                  <MessageSquare className="w-4 h-4 text-[#25D366]" />
                                  <span className="text-sm font-semibold text-gray-900">Send WhatsApp</span>
                                </div>
                              </div>
                              <div className="p-0">
                                <div className="flex items-center border-b border-gray-100 px-4 py-2">
                                  <span className="text-sm text-gray-500 w-16 font-medium">Phone</span>
                                  <input className="flex-1 text-sm outline-none bg-transparent" value={composePhoneTo} onChange={(e) => setComposePhoneTo(e.target.value)} />
                                </div>
                                <div className="flex items-center border-b border-gray-100 px-4 py-2 bg-gray-50/30">
                                   <span className="text-sm text-gray-500 w-[100px] font-medium">Use template</span>
                                   <select className="flex-1 text-sm outline-none bg-transparent text-gray-700 font-medium" value={selectedWhatsappTemplateId} onChange={(e) => setSelectedWhatsappTemplateId(e.target.value)}>
                                      <option value="">Select a template (optional)</option>
                                      {whatsappTemplates.map((tpl) => (
                                          <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                                        ))}
                                   </select>
                                </div>
                                {whatsappTemplateRendering && (
                                  <p className="px-4 py-1 text-xs font-medium text-[#25D366]">Loading template content...</p>
                                )}
                                <div className="p-4">
                                  <textarea className="w-full min-h-[110px] text-sm outline-none resize-none bg-transparent" placeholder="Type your WhatsApp message..." value={whatsappBody} onChange={(e) => setWhatsappBody(e.target.value)} />
                                </div>
                              </div>
                              <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                                 <div className="text-xs text-gray-400 font-medium">
                                   {whatsappBody.length}/1000
                                 </div>
                                 <Button className="h-8 text-xs bg-[#25D366] hover:bg-[#20ba59] text-white shadow-sm px-4" onClick={() => void handleSendWhatsApp("timeline_quick_whatsapp")} disabled={whatsappSendDisabled}>{sendingWhatsapp ? "Sending..." : "Send WhatsApp"}</Button>
                              </div>
                            </div>
                          </div>
                          <div className="lg:col-span-3 space-y-4">
                            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-[#FF5A1F]" />
                                <p className="text-sm font-semibold text-gray-900">Quick Actions</p>
                              </div>
                              <div className="p-2 space-y-1">
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setActiveCommunicationTab("email")}><Mail className="w-4 h-4 text-gray-400"/> Send Email</button>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setActiveCommunicationTab("whatsapp")}><MessageSquare className="w-4 h-4 text-gray-400"/> Send WhatsApp</button>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setReminderChannel("email")}><Calendar className="w-4 h-4 text-gray-400"/> Schedule Reminder</button>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setActiveCommunicationTab("templates")}><FileText className="w-4 h-4 text-gray-400"/> Add Note / Template</button>
                              </div>
                            </div>
                            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <FileText className="w-4 h-4 text-[#FF5A1F]" />
                                  <p className="text-sm font-semibold text-gray-900">Templates</p>
                                </div>
                                <button className="text-[11px] font-medium text-gray-500 hover:text-[#FF5A1F] uppercase tracking-wider" type="button" onClick={() => setActiveCommunicationTab("templates")}>View all</button>
                              </div>
                              <div className="p-2 space-y-1">
                                {communicationTemplates.slice(0, 5).map((tpl) => (
                                  <button key={tpl.id} type="button" onClick={() => { if (tpl.channel === "whatsapp" || tpl.name.toLowerCase().includes("whatsapp")) { setSelectedWhatsappTemplateId(tpl.id); setActiveCommunicationTab("whatsapp"); } else { setSelectedTemplateId(tpl.id); setActiveCommunicationTab("email"); } }} className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors text-left group">
                                    <span className="text-sm text-gray-700 font-medium truncate pr-2 group-hover:text-[#FF5A1F]">{tpl.name}</span>
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 group-hover:text-[#FF5A1F]/70">{tpl.channel === "whatsapp" ? "WA" : "EMAIL"}</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-[#FF5A1F]" />
                                <p className="text-sm font-semibold text-gray-900">Communication Summary</p>
                              </div>
                              <div className="p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-gray-500">Total Interactions</span>
                                  <span className="text-sm font-bold text-gray-900">{communicationSummary.total}</span>
                                </div>
                                <div className="h-px w-full bg-gray-100" />
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-gray-500">Emails Sent</span>
                                  <span className="text-sm font-semibold text-gray-700">{communicationSummary.emails}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-gray-500">WhatsApp Msgs</span>
                                  <span className="text-sm font-semibold text-gray-700">{communicationSummary.whatsapp}</span>
                                </div>
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-gray-500">Replies</span>
                                  <span className="text-sm font-semibold text-gray-700">{communicationSummary.replies}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                  ) : activeCommunicationTab === "email" ? (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                      {/* Left Column: Email Conversations */}
                      <div className="lg:col-span-3 rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm flex flex-col h-[700px]">
                        <div className="p-4 border-b border-gray-100 space-y-4">
                          <h3 className="text-sm font-bold text-gray-900">Email Conversations</h3>
                          <div className="flex gap-2">
                            <div className="relative flex-1">
                              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                              <input className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-md focus:border-[#FF5A1F] outline-none transition-colors" placeholder="Search emails..." value={emailSearch} onChange={(e) => setEmailSearch(e.target.value)} />
                            </div>
                            <select className="border border-gray-200 rounded-md text-sm px-2 py-2 outline-none focus:border-[#FF5A1F] transition-colors font-medium text-gray-700 bg-white">
                              <option>All</option>
                            </select>
                          </div>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                          {communicationMessages.filter(m => m.channel === "email").map((msg, index) => (
                            <div key={msg.id} className={cn("p-4 rounded-xl border cursor-pointer transition-colors relative", index === 0 ? "border-[#FF5A1F] bg-orange-50/30" : "border-gray-100 hover:border-gray-200")}>
                              {index === 0 && <div className="absolute left-[-1px] top-0 bottom-0 w-1 bg-[#FF5A1F] rounded-l-xl" />}
                              <div className="flex items-start gap-3">
                                <Mail className={cn("w-4 h-4 shrink-0 mt-0.5", index === 0 ? "text-[#FF5A1F]" : "text-gray-400")} />
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm font-bold text-gray-900 truncate">{msg.subject || "No Subject"}</p>
                                  <p className="text-xs text-gray-500 truncate mt-1">{msg.body}</p>
                                  <div className="flex items-center justify-between mt-3">
                                    <span className={cn("text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded", (msg.status as string) === "sent" ? "bg-green-100 text-green-700" : (msg.status as string) === "replied" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-700")}>{msg.status as string}</span>
                                    <span className="text-[10px] font-medium text-gray-500">{new Date(msg.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                          {communicationMessages.filter(m => m.channel === "email").length === 0 && (
                            <div className="text-center py-8">
                              <Mail className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                              <p className="text-sm text-gray-500">No emails found.</p>
                            </div>
                          )}
                        </div>
                        <div className="p-3 border-t border-gray-100 bg-gray-50/50">
                          <Button variant="outline" className="w-full text-xs h-9 bg-white hover:bg-gray-50 border-gray-200 text-gray-700">Load more <ChevronDown className="w-3.5 h-3.5 ml-1" /></Button>
                        </div>
                      </div>

                      {/* Middle Column: Compose Email */}
                      <div className="lg:col-span-6 rounded-xl border border-gray-200 bg-white shadow-sm flex flex-col h-[700px]">
                        <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/30">
                          <div className="flex items-center gap-2">
                            <Mail className="w-4 h-4 text-[#FF5A1F]" />
                            <h3 className="text-sm font-bold text-gray-900">Compose Email</h3>
                          </div>
                          <div className="flex items-center gap-4 text-xs font-semibold text-gray-500">
                            <button className="hover:text-gray-900 transition-colors">CC</button>
                            <button className="hover:text-gray-900 transition-colors">BCC</button>
                            <button className="hover:text-gray-900 transition-colors"><Maximize2 className="w-4 h-4" /></button>
                          </div>
                        </div>
                        <div className="p-0 flex-1 flex flex-col overflow-y-auto">
                          <div className="flex items-center px-6 py-3 border-b border-gray-100">
                            <span className="text-sm text-gray-500 w-24 font-medium">To</span>
                            <input className="flex-1 text-sm outline-none bg-transparent border border-gray-200 rounded-lg px-3 py-2 focus:border-[#FF5A1F] transition-colors font-medium text-gray-900" value={composeEmailTo} onChange={(e) => setComposeEmailTo(e.target.value)} />
                          </div>
                          <div className="flex items-center px-6 py-3 border-b border-gray-100">
                            <span className="text-sm text-gray-500 w-24 font-medium">Subject</span>
                            <input className="flex-1 text-sm outline-none bg-transparent border border-gray-200 rounded-lg px-3 py-2 focus:border-[#FF5A1F] transition-colors text-gray-900 font-medium" placeholder="Enter subject..." value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} />
                          </div>
                          <div className="flex items-center px-6 py-3 border-b border-gray-100">
                            <span className="text-sm text-gray-500 w-24 font-medium">Use Template</span>
                            <select className="flex-1 text-sm outline-none bg-transparent border border-gray-200 rounded-lg px-3 py-2 focus:border-[#FF5A1F] transition-colors text-gray-900 font-medium" value={selectedTemplateId} onChange={(e) => setSelectedTemplateId(e.target.value)}>
                              <option value="">No template (manual)</option>
                              {emailTemplates.map((tpl) => (
                                <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                              ))}
                            </select>
                          </div>
                          {emailTemplateRendering && (
                            <p className="px-6 pt-2 text-xs font-medium text-[#FF5A1F]">Loading template content...</p>
                          )}
                          
                          <div className="flex items-center gap-1.5 px-6 py-2 border-b border-gray-100 bg-gray-50/50">
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Bold"><Bold className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Italic"><Italic className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Underline"><Underline className="w-4 h-4" /></button>
                            <div className="w-px h-5 bg-gray-200 mx-1" />
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Bullet List"><ListIcon className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Numbered List"><ListOrdered className="w-4 h-4" /></button>
                            <div className="w-px h-5 bg-gray-200 mx-1" />
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Link"><LinkIcon className="w-4 h-4" /></button>
                          </div>
                          
                          <div className="px-6 py-4 flex-1 flex flex-col min-h-[200px]">
                            <textarea className="w-full h-full text-sm outline-none resize-none bg-transparent text-gray-800 leading-relaxed font-medium" placeholder="Write your email here..." value={emailBody} onChange={(e) => setEmailBody(e.target.value)} />
                          </div>

                          {attachments.length > 0 && (
                            <div className="px-6 pb-4">
                              <p className="text-xs font-semibold text-gray-500 flex items-center gap-1.5 mb-3">
                                <Paperclip className="w-3.5 h-3.5" /> {attachments.length} Attachment{attachments.length > 1 ? 's' : ''}
                              </p>
                              <div className="flex flex-col gap-2">
                                {attachments.map((a, i) => (
                                  <div key={i} className="flex items-center justify-between border border-gray-200 rounded-lg p-3 bg-gray-50/50 hover:bg-gray-50 transition-colors">
                                    <div className="flex items-center gap-3">
                                      <FileText className="w-4 h-4 text-gray-400" />
                                      <span className="text-sm font-medium text-gray-700">{a.filename}</span>
                                    </div>
                                    <div className="flex items-center gap-4">
                                      <span className="text-xs font-medium text-gray-500">{(a.content_base64.length / 1024).toFixed(0)} KB</span>
                                      <button className="text-gray-400 hover:text-red-500 transition-colors p-1"><X className="w-4 h-4" /></button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                        
                        <div className="px-6 py-4 bg-gray-50/30 border-t border-gray-100 flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <label className="cursor-pointer hover:text-[#FF5A1F] text-gray-600 transition-colors flex items-center gap-1.5 font-semibold text-sm">
                              <Paperclip className="w-4 h-4" /> 
                              <span>Attach File</span>
                              <input type="file" className="hidden" onChange={(e) => void handleAttachmentSelected(e.target.files?.[0] ?? null)} />
                            </label>
                            <button
                              className="text-xs text-red-500 font-medium hover:text-red-600 transition-colors"
                              type="button"
                              onClick={() => void handleDisconnectProvider(selectedEmailProvider)}
                            >
                              Disconnect {selectedEmailProvider}
                            </button>
                          </div>
                          <div className="flex items-center gap-3">
                            <Button variant="outline" className="h-10 text-sm font-semibold text-gray-700 bg-white border-gray-200 hover:bg-gray-50 hover:text-gray-900 shadow-sm" onClick={() => void handleSendEmail(true, "save_draft")} disabled={emailDraftDisabled}>
                              Save Draft
                            </Button>
                            <Button className="h-10 text-sm font-bold bg-[#FF5A1F] hover:bg-[#E54E1A] text-white px-6 shadow-sm flex items-center gap-2" onClick={() => void handleSendEmail(false, "quick_send")} disabled={emailSendDisabled}>
                              {sendingEmail ? "Sending..." : "Send Email"} <ChevronDown className="w-4 h-4 opacity-70" />
                            </Button>
                          </div>
                        </div>
                      </div>

                      {/* Right Column: Details & Templates */}
                      <div className="lg:col-span-3 space-y-6">
                        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5 space-y-5">
                          <div className="flex items-center gap-2 mb-1">
                            <Mail className="w-4 h-4 text-[#FF5A1F]" />
                            <h3 className="text-sm font-bold text-gray-900">Email Details</h3>
                          </div>
                          <div className="space-y-4">
                            <div className="flex flex-col gap-1.5">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">From</span>
                              <span className="text-sm font-semibold text-gray-900">{recruiterName}</span>
                            </div>
                            <div className="flex flex-col gap-1.5">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Email Signature</span>
                              <span className="text-sm font-semibold text-gray-900">Default Signature</span>
                            </div>
                            <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                              <span className="text-xs font-semibold text-gray-700">Track Email</span>
                              <div className="w-8 h-4.5 bg-[#FF5A1F] rounded-full relative cursor-pointer shadow-inner">
                                <div className="w-3.5 h-3.5 bg-white rounded-full absolute right-0.5 top-0.5 shadow-sm" />
                              </div>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-gray-700">Request Read Receipt</span>
                              <div className="w-8 h-4.5 bg-gray-200 rounded-full relative cursor-pointer shadow-inner">
                                <div className="w-3.5 h-3.5 bg-white rounded-full absolute left-0.5 top-0.5 shadow-sm" />
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                              <Mail className="w-4 h-4 text-[#FF5A1F]" />
                              <h3 className="text-sm font-bold text-gray-900">Email Templates</h3>
                            </div>
                            <button className="text-[10px] font-bold uppercase text-gray-500 hover:text-[#FF5A1F] tracking-wider transition-colors" onClick={() => setActiveCommunicationTab("templates")}>View All</button>
                          </div>
                          <div className="space-y-2">
                            {emailTemplates.length > 0 ? emailTemplates.slice(0, 6).map(tpl => (
                              <div key={tpl.id} className="flex items-center justify-between p-2.5 rounded-lg hover:bg-gray-50 border border-transparent hover:border-gray-100 cursor-pointer transition-colors group" onClick={() => setSelectedTemplateId(tpl.id)}>
                                <span className="text-xs font-semibold text-gray-700 truncate pr-2 group-hover:text-[#FF5A1F] transition-colors">{tpl.name}</span>
                                <span className="text-[9px] font-bold px-2 py-0.5 bg-green-50 text-green-700 rounded uppercase tracking-wider shrink-0 border border-green-100">Email</span>
                              </div>
                            )) : (
                              <p className="text-xs text-gray-500 text-center py-4">No templates found.</p>
                            )}
                          </div>
                        </div>

                        <div className="bg-blue-50/50 rounded-xl p-4 border border-blue-100 flex items-start gap-3">
                          <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center shadow-sm shrink-0 mt-0.5 border border-blue-50">
                            <span className="text-xs">💡</span>
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-blue-900 mb-1">Tip</h4>
                            <p className="text-xs text-blue-800 leading-relaxed font-medium">Use templates to save time and maintain consistent communication.</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : activeCommunicationTab === "whatsapp" ? (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                      {/* Left Column: WhatsApp Conversations */}
                      <div className="lg:col-span-3 rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm flex flex-col h-[700px]">
                        <div className="p-4 border-b border-gray-100 space-y-4">
                          <h3 className="text-sm font-bold text-gray-900">WhatsApp Conversations</h3>
                          <div className="flex gap-2">
                            <div className="relative flex-1">
                              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                              <input className="w-full pl-9 pr-3 py-2 text-[13px] border border-gray-200 rounded-md focus:border-[#25D366] outline-none transition-colors shadow-sm" placeholder="Search messages..." value={whatsappSearch} onChange={(e) => setWhatsappSearch(e.target.value)} />
                            </div>
                            <select className="border border-gray-200 rounded-md text-sm px-2 py-2 outline-none focus:border-[#25D366] transition-colors font-medium text-gray-700 bg-white">
                              <option>All</option>
                            </select>
                          </div>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                          {communicationMessages.filter(m => m.channel === "whatsapp").map((msg, index) => (
                            <div key={msg.id} className={cn("p-4 rounded-xl border cursor-pointer transition-colors relative", index === 0 ? "border-[#25D366] bg-green-50/30" : "border-gray-100 hover:border-gray-200")}>
                              {index === 0 && <div className="absolute left-[-1px] top-0 bottom-0 w-1 bg-[#25D366] rounded-l-xl" />}
                              <div className="flex items-start gap-3">
                                <MessageSquare className={cn("w-4 h-4 shrink-0 mt-0.5", index === 0 ? "text-[#25D366]" : "text-[#25D366]/60")} />
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm font-bold text-gray-900 truncate">{msg.subject || "Message"}</p>
                                  <p className="text-xs text-gray-500 truncate mt-1">{msg.body}</p>
                                  <div className="flex items-center justify-between mt-3">
                                    <span className={cn("text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded", msg.status === "sent" ? "bg-green-100 text-green-700" : (msg.status as string) === "replied" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-700")}>{msg.status as string}</span>
                                    <span className="text-[10px] font-medium text-gray-500">{new Date(msg.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                          {communicationMessages.filter(m => m.channel === "whatsapp").length === 0 && (
                            <div className="text-center py-8">
                              <MessageSquare className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                              <p className="text-sm text-gray-500">No WhatsApp messages found.</p>
                            </div>
                          )}
                        </div>
                        <div className="p-3 border-t border-gray-100 bg-gray-50/50">
                          <Button variant="outline" className="w-full text-xs h-9 bg-white hover:bg-gray-50 border-gray-200 text-gray-700">Load more <ChevronDown className="w-3.5 h-3.5 ml-1" /></Button>
                        </div>
                      </div>

                      {/* Middle Column: Send WhatsApp */}
                      <div className="lg:col-span-6 rounded-xl border border-gray-200 bg-white shadow-sm flex flex-col h-[700px]">
                        <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/30">
                          <div className="flex items-center gap-2">
                            <MessageSquare className="w-4 h-4 text-[#25D366]" />
                            <h3 className="text-sm font-bold text-gray-900">Send WhatsApp Message</h3>
                          </div>
                          <div className="flex items-center gap-4 text-xs font-semibold text-gray-500">
                            <button className="hover:text-gray-900 transition-colors"><Maximize2 className="w-4 h-4" /></button>
                          </div>
                        </div>
                        <div className="p-0 flex-1 flex flex-col overflow-y-auto">
                          <div className="flex items-center px-6 py-3 border-b border-gray-100">
                            <span className="text-sm text-gray-500 w-28 font-medium">To</span>
                            <input className="flex-1 text-sm outline-none bg-transparent border border-gray-200 rounded-lg px-3 py-2 focus:border-[#25D366] transition-colors font-medium text-gray-900" value={composePhoneTo} onChange={(e) => setComposePhoneTo(e.target.value)} />
                          </div>
                          <div className="flex items-center px-6 py-3 border-b border-gray-100">
                            <span className="text-sm text-gray-500 w-28 font-medium">Use Template</span>
                            <div className="flex-1 flex gap-2">
                              <select className="flex-1 text-sm outline-none bg-transparent border border-gray-200 rounded-lg px-3 py-2 focus:border-[#25D366] transition-colors text-gray-900 font-medium" value={selectedWhatsappTemplateId} onChange={(e) => setSelectedWhatsappTemplateId(e.target.value)}>
                                <option value="">Manual message</option>
                                {whatsappTemplates.map((tpl) => (
                                  <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                                ))}
                              </select>
                              <Button variant="outline" className="h-9 px-3 text-xs bg-white text-gray-700 hover:bg-gray-50" disabled={!selectedWhatsappTemplateId || whatsappTemplateRendering} onClick={() => selectedWhatsappTemplateId && void fillWhatsAppFromTemplate(selectedWhatsappTemplateId)}>
                                {whatsappTemplateRendering ? "Loading..." : "Preview Template"}
                              </Button>
                            </div>
                          </div>
                          {templatePreview && selectedWhatsappTemplateId ? (
                            <div className="mx-6 mt-3 rounded-lg border border-green-100 bg-green-50/50 p-3 text-xs text-green-900 whitespace-pre-wrap">
                              {templatePreview}
                            </div>
                          ) : null}
                          
                          <div className="flex items-center gap-1.5 px-6 py-2 border-b border-gray-100 bg-gray-50/50">
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Bold"><Bold className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Italic"><Italic className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Underline"><Underline className="w-4 h-4" /></button>
                            <div className="w-px h-5 bg-gray-200 mx-1" />
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Bullet List"><ListIcon className="w-4 h-4" /></button>
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Numbered List"><ListOrdered className="w-4 h-4" /></button>
                            <div className="w-px h-5 bg-gray-200 mx-1" />
                            <button className="p-1.5 rounded-md hover:bg-white border border-transparent hover:border-gray-200 hover:shadow-sm text-gray-600 transition-all" title="Link"><LinkIcon className="w-4 h-4" /></button>
                          </div>
                          
                          <div className="px-6 py-4 flex-1 flex flex-col min-h-[200px] relative">
                            <textarea className="w-full h-full text-sm outline-none resize-none bg-transparent text-gray-800 leading-relaxed font-medium pb-6" placeholder="Write WhatsApp message..." value={whatsappBody} onChange={(e) => setWhatsappBody(e.target.value)} />
                            <span className="absolute bottom-4 right-6 text-xs text-gray-400 font-medium">Characters: {whatsappBody.length}</span>
                          </div>

                          <div className="px-6 pb-4">
                            <div className="border border-dashed border-gray-300 rounded-lg p-4 bg-gray-50/50 flex flex-col gap-2">
                              <p className="text-xs font-semibold text-gray-500 flex items-center gap-1.5">
                                <Paperclip className="w-3.5 h-3.5" /> Add Attachment (Optional)
                              </p>
                              <div className="flex items-center gap-3">
                                <Button variant="outline" className="h-8 text-xs bg-white shadow-sm border-gray-200 text-gray-700 hover:bg-gray-50">
                                  <FileText className="w-3 h-3 mr-1.5" /> Upload file
                                </Button>
                                <span className="text-[10px] text-gray-400 font-medium uppercase tracking-wider">PDF, DOC, DOCX, PNG, JPG (Max 10MB)</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div className="px-6 py-4 bg-gray-50/30 border-t border-gray-100 flex items-center justify-between">
                          <div className="text-xs font-semibold text-gray-400">
                            {whatsappBody.length}/1000
                          </div>
                          <Button className="h-10 text-sm font-bold bg-[#FF5A1F] hover:bg-[#E54E1A] text-white px-6 shadow-sm flex items-center gap-2" onClick={() => void handleSendWhatsApp("interview_reminder")} disabled={whatsappSendDisabled}>
                            {sendingWhatsapp ? "Sending..." : "Send WhatsApp"}
                          </Button>
                        </div>
                      </div>

                      {/* Right Column: Details & Templates */}
                      <div className="lg:col-span-3 space-y-6">
                        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5 space-y-5">
                          <div className="flex items-center gap-2 mb-1">
                            <MessageSquare className="w-4 h-4 text-[#25D366]" />
                            <h3 className="text-sm font-bold text-gray-900">WhatsApp Contact</h3>
                          </div>
                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Name</span>
                              <span className="text-sm font-semibold text-gray-900">{candidate.first_name} {candidate.last_name}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Phone</span>
                              <span className="text-sm font-semibold text-gray-900">{candidate.phone || "-"}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Status</span>
                              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-green-100 text-green-700 rounded border border-green-200">Active</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Opted In</span>
                              <span className="text-sm font-semibold text-gray-900">Yes</span>
                            </div>
                          </div>
                        </div>

                        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                              <MessageSquare className="w-4 h-4 text-[#25D366]" />
                              <h3 className="text-sm font-bold text-gray-900">Message Templates</h3>
                            </div>
                            <button className="text-[10px] font-bold uppercase text-gray-500 hover:text-[#25D366] tracking-wider transition-colors" onClick={() => setActiveCommunicationTab("templates")}>View All</button>
                          </div>
                          <div className="space-y-2">
                            {whatsappTemplates.length > 0 ? 
                              whatsappTemplates.slice(0, 6).map(tpl => (
                              <div key={tpl.id} className="flex items-center justify-between p-2.5 rounded-lg hover:bg-gray-50 border border-transparent hover:border-gray-100 cursor-pointer transition-colors group" onClick={() => setSelectedWhatsappTemplateId(tpl.id)}>
                                <span className="text-xs font-semibold text-gray-700 truncate pr-2 group-hover:text-[#25D366] transition-colors">{tpl.name}</span>
                                <span className="text-[9px] font-bold px-2 py-0.5 bg-green-50 text-green-700 rounded uppercase tracking-wider shrink-0 border border-green-100">WhatsApp</span>
                              </div>
                            )) : (
                              <p className="text-xs text-gray-500 text-center py-4">No WhatsApp templates found.</p>
                            )}
                          </div>
                        </div>

                        <div className="bg-green-50/50 rounded-xl p-4 border border-green-100 flex items-start gap-3">
                          <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center shadow-sm shrink-0 mt-0.5 border border-green-50">
                            <span className="text-xs">💡</span>
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-green-900 mb-1">Tip</h4>
                            <p className="text-xs text-green-800 leading-relaxed font-medium">Use templates to save time and maintain consistent communication.</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[800px]">
                      {/* Left Column: List */}
                      <div className="lg:col-span-3 flex flex-col border-r border-gray-100 pr-6">
                        <div className="space-y-4 mb-4">
                          <h3 className="text-lg font-bold text-gray-900">Templates</h3>
                          <div className="flex gap-2">
                            <div className="relative flex-1">
                              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                              <input className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-md focus:border-[#FF5A1F] outline-none transition-colors" placeholder="Search templates..." value={templateSearch} onChange={(e) => setTemplateSearch(e.target.value)} />
                            </div>
                            <button className="p-2 border border-gray-200 rounded-md text-gray-500 hover:bg-gray-50 transition-colors flex items-center justify-center shrink-0">
                              <Filter className="w-4 h-4" />
                            </button>
                          </div>
                          <select className="w-full border border-gray-200 rounded-md text-sm px-3 py-2 outline-none focus:border-[#FF5A1F] transition-colors font-medium text-gray-700 bg-white" value={templateCategoryFilter} onChange={(e) => setTemplateCategoryFilter(e.target.value)}>
                            <option value="all">All Channels</option>
                            <option value="email">Email</option>
                            <option value="whatsapp">WhatsApp</option>
                          </select>
                          <button className="flex items-center gap-2 px-4 py-2 bg-[#1A1F2C] text-white rounded-lg hover:bg-[#2A2F3C] transition-all font-bold text-[13px] shadow-sm w-full justify-center" onClick={() => { setSelectedTemplateId(""); setIsEditingTemplate(false); setNewTemplateName(""); setNewTemplateBody(""); setNewTemplateSubject(""); }}>
                              <Plus className="w-4 h-4" /> New Template
                          </button>
                        </div>

                        <div className="flex-1 overflow-y-auto space-y-2 pr-1 -mr-1">
                          {communicationTemplates.length > 0 ? (
                             communicationTemplates.filter(t => templateCategoryFilter === 'all' || t.channel === templateCategoryFilter).filter(t => t.name.toLowerCase().includes(templateSearch.toLowerCase())).map((tpl) => (
                               <div key={tpl.id} className={cn("p-4 rounded-xl border cursor-pointer transition-all relative group", selectedTemplateId === tpl.id ? "border-[#FF5A1F] bg-orange-50/30 shadow-sm" : "border-transparent hover:border-gray-200 hover:bg-gray-50/50")} onClick={() => setSelectedTemplateId(tpl.id)}>
                                  {selectedTemplateId === tpl.id && <div className="absolute left-[-1px] top-0 bottom-0 w-[3px] bg-[#FF5A1F] rounded-l-xl" />}
                                  <div className="flex items-start justify-between gap-2 mb-1.5">
                                    <div className="flex items-center gap-2">
                                      {tpl.channel === "whatsapp" || (tpl.name || "").toLowerCase().includes("whatsapp") ? <MessageSquare className={cn("w-4 h-4 shrink-0", selectedTemplateId === tpl.id ? "text-[#25D366]" : "text-[#25D366]/70")} /> : <Mail className={cn("w-4 h-4 shrink-0", selectedTemplateId === tpl.id ? "text-[#FF5A1F]" : "text-[#FF5A1F]/70")} />}
                                      <span className={cn("text-[13px] font-bold truncate", selectedTemplateId === tpl.id ? "text-gray-900" : "text-gray-700")}>{tpl.name}</span>
                                      <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0", tpl.channel === "whatsapp" || (tpl.name || "").toLowerCase().includes("whatsapp") ? "bg-green-50 text-green-700" : "bg-green-50 text-green-700")}>{tpl.channel === "whatsapp" || (tpl.name || "").toLowerCase().includes("whatsapp") ? "WhatsApp" : "Email"}</span>
                                    </div>
                                    <button className="text-gray-400 hover:text-gray-600 transition-colors"><MoreVertical className="w-4 h-4" /></button>
                                  </div>
                                  <p className="text-[11px] text-gray-500 line-clamp-1 mb-2">{tpl.subject_template || tpl.body_template}</p>
                                  <span className="text-[10px] text-gray-400 font-medium">Updated {new Date(tpl.updated_at).toLocaleDateString()}</span>
                               </div>
                             ))
                          ) : (
                            <div className="text-center py-8">
                              <p className="text-sm text-gray-500">No templates found.</p>
                            </div>
                          )}
                        </div>
                        <div className="pt-4 border-t border-gray-100 flex items-center justify-between mt-auto shrink-0 mb-2">
                          <span className="text-xs text-gray-500 font-medium">Showing 1 to {Math.min(communicationTemplates.length, 6)} of {communicationTemplates.length} templates</span>
                          <button className="text-xs font-bold text-[#FF5A1F] hover:text-[#E54E1A] transition-colors">View all</button>
                        </div>
                      </div>

                      {/* Right Column: Editor & Preview Area */}
                      <div className="lg:col-span-9 flex flex-col h-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                        {/* Header */}
                        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-10 shrink-0">
                          <div className="flex items-center gap-3">
                            <button className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500 transition-colors" onClick={() => { setSelectedTemplateId(""); setIsEditingTemplate(false); }}><ChevronLeft className="w-4 h-4" /></button>
                            <div>
                              <div className="flex items-center gap-2 mb-0.5">
                                <h2 className="text-[17px] font-bold text-gray-900 tracking-tight">{(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.name : (isEditingTemplate ? "Edit Template" : "Create New Template")}</h2>
                                {(selectedTemplateId && !isEditingTemplate) && (
                                  <button className="text-gray-400 hover:text-[#FF5A1F] transition-colors ml-1" onClick={handleEditExistingTemplate}><Edit3 className="w-3.5 h-3.5" /></button>
                                )}
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="px-2 py-0.5 bg-green-50 text-green-600 text-[10px] font-bold uppercase tracking-wider rounded border border-green-100 flex items-center gap-1">
                                  {(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.channel : (newTemplateCategory)}
                                </span>
                                <span className="text-[11px] text-gray-400 font-medium">Auto-saved Just now</span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"><Maximize2 className="w-4 h-4" /></button>
                            <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors" onClick={() => { setSelectedTemplateId(""); setIsEditingTemplate(false); }}><X className="w-4 h-4" /></button>
                          </div>
                        </div>

                        {/* Main Content: Split Grid */}
                        <div className="flex-1 overflow-y-auto p-8 bg-gray-50/30">
                          <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 h-full min-h-0">
                            {/* Editor Column */}
                            <div className="lg:col-span-7 flex flex-col gap-6">
                              <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                  <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider ml-1">Template name</label>
                                  <Input 
                                    className="text-[13px] h-10 focus-visible:ring-[#FF5A1F] border-gray-200 rounded-lg font-medium bg-white" 
                                    placeholder="e.g. Interview Reminder" 
                                    value={(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.name || "" : newTemplateName} 
                                    onChange={(e) => (selectedTemplateId && !isEditingTemplate) ? null : setNewTemplateName(e.target.value)} 
                                    disabled={!!selectedTemplateId && !isEditingTemplate} 
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider ml-1">Channel</label>
                                  <div className="relative">
                                    <select 
                                      className="w-full h-10 px-3 pr-10 text-[13px] border border-gray-200 rounded-lg focus:border-[#FF5A1F] outline-none transition-colors appearance-none font-medium bg-white disabled:bg-gray-50 disabled:text-gray-500" 
                                      value={(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.channel : newTemplateCategory} 
                                      onChange={(e) => (selectedTemplateId && !isEditingTemplate) ? null : setNewTemplateCategory(e.target.value)} 
                                      disabled={!!selectedTemplateId && !isEditingTemplate}
                                    >
                                      <option value="email">Email</option>
                                      <option value="whatsapp">WhatsApp</option>
                                    </select>
                                    <ChevronDown className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                                  </div>
                                </div>
                              </div>

                              <div className="space-y-1.5">
                                <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider ml-1">Subject</label>
                                <Input 
                                  className="text-[13px] h-10 focus-visible:ring-[#FF5A1F] border-gray-200 rounded-lg font-medium bg-white" 
                                  placeholder="e.g. Reminder: Upcoming Interview" 
                                  value={(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.subject_template || "" : newTemplateSubject} 
                                  onChange={(e) => (selectedTemplateId && !isEditingTemplate) ? null : setNewTemplateSubject(e.target.value)} 
                                  disabled={!!selectedTemplateId && !isEditingTemplate} 
                                />
                              </div>

                              <div className="space-y-1.5 flex-1 flex flex-col min-h-[400px]">
                                <div className="flex items-center justify-between ml-1">
                                  <label className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">Template Content</label>
                                  <span className="text-[10px] text-gray-400 font-medium">Markdown supported</span>
                                </div>
                                <div className="flex-1 flex flex-col border border-gray-200 rounded-xl bg-white shadow-sm overflow-hidden">
                                  <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex items-center gap-1">
                                    <button className="p-1.5 rounded-md hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 text-[#FF5A1F] transition-all flex items-center gap-1.5 text-[11px] font-bold mr-2" onClick={() => insertVariable("{{candidate_name}}")}><Plus className="w-3.5 h-3.5" /> Variable</button>
                                    <div className="w-px h-5 bg-gray-200 mx-2" />
                                    <button className="p-1.5 rounded-md hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 text-gray-600 transition-all"><Bold className="w-3.5 h-3.5" /></button>
                                    <button className="p-1.5 rounded-md hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 text-gray-600 transition-all"><Italic className="w-3.5 h-3.5" /></button>
                                    <button className="p-1.5 rounded-md hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 text-gray-600 transition-all"><Underline className="w-3.5 h-3.5" /></button>
                                  </div>
                                  <textarea
                                    ref={templateEditorRef}
                                    className="flex-1 w-full p-5 text-[13px] outline-none resize-none text-gray-800 font-medium leading-relaxed"
                                    placeholder="Write your template body..."
                                    value={(selectedTemplateId && !isEditingTemplate) ? communicationTemplates.find(t => t.id === selectedTemplateId)?.body_template || "" : newTemplateBody}
                                    onChange={(e) => (selectedTemplateId && !isEditingTemplate) ? null : setNewTemplateBody(e.target.value)}
                                    disabled={!!selectedTemplateId && !isEditingTemplate}
                                  />
                                </div>
                              </div>
                              
                              <div className="flex items-center justify-end gap-3 shrink-0">
                                <Button variant="outline" className="h-9 px-6 text-xs font-bold border-gray-200 text-gray-700 hover:bg-gray-50 rounded-lg" onClick={() => { setSelectedTemplateId(""); setIsEditingTemplate(false); }}>Cancel</Button>
                                <Button className="h-9 px-6 text-xs font-bold bg-[#FF5A1F] hover:bg-[#E54E1A] text-white shadow-sm rounded-lg" onClick={() => (selectedTemplateId && !isEditingTemplate) ? handleUseSelectedTemplate() : void handleSaveTemplate()}>
                                  {(selectedTemplateId && !isEditingTemplate) ? "Use Template" : (isEditingTemplate ? "Update Template" : "Save Template")}
                                </Button>
                              </div>
                            </div>

                            {/* Preview Column */}
                            <div className="lg:col-span-5 flex flex-col gap-6">
                              <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                                <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-white shrink-0">
                                  <h3 className="text-[13px] font-bold text-gray-900 tracking-tight">Preview</h3>
                                  <div className="flex items-center bg-gray-100/80 rounded-md p-0.5 border border-gray-200/50">
                                    <button className="px-3 py-1.5 text-[11px] font-bold text-gray-500 hover:text-gray-700 transition-colors rounded-sm" onClick={() => { if (selectedTemplateId && !isEditingTemplate) handleEditExistingTemplate(); else templateEditorRef.current?.focus(); }}>Edit</button>
                                    <button className="px-3 py-1.5 text-[11px] font-bold bg-white text-[#FF5A1F] rounded-sm shadow-sm border border-gray-200">Preview</button>
                                  </div>
                                </div>
                                <div className="flex-1 overflow-y-auto p-6 bg-white">
                                  {(() => {
                                    const rawBody = (selectedTemplateId && !isEditingTemplate)
                                      ? communicationTemplates.find(t => t.id === selectedTemplateId)?.body_template || "" 
                                      : newTemplateBody;
                                      
                                    if (!rawBody) return <p className="text-sm text-gray-400 italic">No preview available. Start typing to see a preview.</p>;

                                    const replacedBody = previewTemplateText(rawBody);

                                    return (
                                      <pre className="text-[13px] text-gray-800 font-sans whitespace-pre-wrap leading-relaxed">{replacedBody}</pre>
                                    );
                                  })()}
                                </div>
                              </div>
                              
                              <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                                <h3 className="text-[13px] font-bold text-gray-900 mb-3 tracking-tight">Recently used variables</h3>
                                <div className="flex flex-wrap gap-2 mb-4">
                                  {["{{candidate_name}}", "{{job_title}}", "{{interview_date}}", "{{interview_time}}", "{{company_name}}"].map((field) => (
                                    <button key={field} onClick={() => insertVariable(field)} className="px-3 py-1.5 rounded-md border border-gray-200 bg-white shadow-sm text-[11px] font-mono font-medium text-gray-600 hover:border-[#FF5A1F] hover:text-[#FF5A1F] transition-colors">{field}</button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      
                      {/* Footer Bar */}
                        <div className="px-6 py-4 border-t border-gray-100 bg-white flex items-center justify-end gap-3 shrink-0">
                          <Button variant="outline" className="h-9 px-6 text-xs font-bold bg-white shadow-sm border-gray-200 text-gray-700 hover:bg-gray-50 rounded-lg" onClick={() => setSelectedTemplateId("")}>Cancel</Button>
                          <Button className="h-9 px-6 text-xs font-bold bg-[#FF5A1F] hover:bg-[#E54E1A] text-white shadow-sm rounded-lg" disabled={!!selectedTemplateId && !isEditingTemplate ? false : (creatingTemplate || !newTemplateName || !newTemplateBody)} onClick={() => (selectedTemplateId && !isEditingTemplate) ? handleUseSelectedTemplate() : void handleSaveTemplate()}>
                            {(selectedTemplateId && !isEditingTemplate) ? "Use Template" : (selectedTemplateId ? "Update Template" : (creatingTemplate ? "Saving..." : "Save Template"))}
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="rounded-md border border-gray-200 p-3">
                    <p className="text-xs font-medium text-gray-600 mb-2">Reminder Scheduling</p>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                      <select className="rounded-md border border-gray-200 px-2 py-1.5 text-sm" value={reminderChannel} onChange={(e) => setReminderChannel(e.target.value as "email" | "whatsapp")}>
                        <option value="email">Email</option>
                        <option value="whatsapp">WhatsApp</option>
                      </select>
                      <Input type="datetime-local" value={reminderAt} onChange={(e) => setReminderAt(e.target.value)} />
                      <Button variant="outline" disabled={reminderDisabled} onClick={() => void handleCreateReminder()}>{schedulingReminder ? "Scheduling..." : "Schedule Reminder"}</Button>
                      <Button variant="outline" disabled={runningReminders} onClick={() => void handleRunDueReminders()}>{runningReminders ? "Running..." : "Run Due Jobs"}</Button>
                    </div>
                    {communicationReminders.length > 0 ? (
                      <div className="mt-3 space-y-1">
                        {communicationReminders.slice(0, 5).map((r) => (
                          <p key={r.id} className="text-xs text-gray-600">
                            {r.channel.toUpperCase()} {new Date(r.scheduled_for).toLocaleString()} - {r.status}
                          </p>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-xs text-gray-500">No reminders scheduled yet.</p>
                    )}
                  </div>
                  {communicationConnections.length > 0 ? (
                    <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
                      <p className="text-xs font-medium text-gray-600 mb-2">Connected providers</p>
                      <div className="flex flex-wrap gap-2">
                        {communicationConnections.map((conn) => (
                          <span key={conn.id} className="rounded-full bg-white border border-gray-200 px-2.5 py-1 text-xs">
                            {conn.provider}: {conn.external_account_email || conn.status}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Timeline & Interviews */}
      {activeTab !== "communication" && (
      <div className="space-y-6">

        {/* Interviews */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50/50 p-5 flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#FF5A1F]" /> Interviews
              {interviews.length > 0 && (
                <span className="text-xs font-normal text-gray-500">({interviews.length})</span>
              )}
            </h2>
            {pipelines.length > 0 && (
              <div className="relative group/sched">
                <Button
                  className="h-7 text-xs bg-[#FF5A1F] hover:bg-[#E54E1A] text-white disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => setSchedulingModalOpen(true)}
                  disabled={eligiblePipelines.length === 0}
                >
                  <Plus className="w-3.5 h-3.5 mr-1" /> Schedule
                </Button>
                {eligiblePipelines.length === 0 && (
                  <div className="absolute bottom-full right-0 mb-1.5 hidden group-hover/sched:block z-10 w-52 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg">
                    Move the candidate to Screening before scheduling interviews.
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="p-4">
            <InterviewList
              interviews={interviews}
              onInterviewsChange={setInterviews}
              onRefresh={refreshInterviewData}
              canUpdate
              canDelete
              canFeedback
              emptyMessage={
                eligiblePipelines.length > 0
                  ? "No interviews yet. Click Schedule to add one."
                  : pipelines.length > 0
                  ? "Move candidate to Screening or later to schedule interviews."
                  : "Submit candidate to a job first to schedule interviews."
              }
            />
          </div>
        </div>

        {/* Interview Timeline */}
        {interviews.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="border-b border-gray-100 bg-gray-50/50 p-5">
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#FF5A1F]" /> Interview Timeline
              </h2>
            </div>
            <div className="p-5">
              <InterviewTimeline interviews={interviews} />
            </div>
          </div>
        )}

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



        </div >
      )}
      </div >

      {eligiblePipelines.length > 0 && (
        <ScheduleInterviewModal
          pipelines={eligiblePipelines}
          jobs={jobs}
          open={schedulingModalOpen}
          onClose={() => setSchedulingModalOpen(false)}
          onCreated={(interview) => {
            setInterviews((prev) => [interview, ...prev]);
            void refreshInterviewData();
          }}
        />
      )}
    </section >
  );
}
