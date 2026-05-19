"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import {
  addCandidateInteraction,
  bulkDeleteCandidates,
  bulkHardDeleteCandidates,
  bulkUnarchiveCandidates,
  bulkAssignRecruiter,
  getCandidateInteractions,
  createBulkUploadJob,
  createCandidate,
  getBulkUploadJobStatus,
  getCandidatesPage,
  isDefaultCandidatesListFilters,
  readCachedCandidatesListPage,
  writeCachedCandidatesListPage,
  type CandidateManagementParseResult,
  type BulkUploadJobStatus,
  type CandidateInteraction,
  updateCandidate,
  uploadResumeForReview,
} from "@/lib/api/candidates";
import { getJobsForSelect, submitCandidateToJob } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
import type { Candidate, Job, OrganizationUser, Pipeline } from "@/lib/api/types";
import { getUsers } from "@/lib/api/users";
import { CANDIDATES_CREATE_PERMISSION, hasPermission } from "@/lib/rbac";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Users, UserPlus, Search, Calendar, Eye, FileText, ArchiveRestore, MoreVertical, Trash2, ChevronDown } from "lucide-react";

type AddMode = "manual" | "resume" | "csv";

type CandidateDraft = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  location: string;
  headline: string;
  years_experience: string;
  summary: string;
  resume_s3_key: string;
  resume_file_name: string;
};

type SlotDraft = {
  startAt: string;
  note: string;
};

type CandidateCreatedAtSort = "newest" | "oldest";

const CREATED_AT_SORT_OPTIONS: { value: CandidateCreatedAtSort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
];

function compareCandidatesByCreatedAt(a: Candidate, b: Candidate, sort: CandidateCreatedAtSort): number {
  const aTime = new Date(a.created_at).getTime();
  const bTime = new Date(b.created_at).getTime();
  if (Number.isNaN(aTime) || Number.isNaN(bTime)) {
    return 0;
  }
  return sort === "newest" ? bTime - aTime : aTime - bTime;
}

export default function CandidatesPage() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Candidate[]>(
    () => readCachedCandidatesListPage()?.candidates ?? []
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(() => readCachedCandidatesListPage() === null);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [savingReview, setSavingReview] = useState(false);
  const [bulkCreating, setBulkCreating] = useState(false);
  const [bulkPolling, setBulkPolling] = useState(false);
  const [viewImportedOnly, setViewImportedOnly] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [addMode, setAddMode] = useState<AddMode>("manual");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [candidateRole, setCandidateRole] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [summary, setSummary] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvResumeKeys, setCsvResumeKeys] = useState("");
  const [bulkJob, setBulkJob] = useState<BulkUploadJobStatus | null>(null);
  const [draftCandidate, setDraftCandidate] = useState<CandidateDraft | null>(null);
  const [parseResult, setParseResult] = useState<CandidateManagementParseResult | null>(null);
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [slots, setSlots] = useState<SlotDraft[]>([{ startAt: "", note: "" }]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const searchDebounceBootstrappedRef = useRef(false);
  const [locationFilter, setLocationFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived" | "deleted">("all");
  const [stageFilter, setStageFilter] = useState<
    "all" | "applied" | "screening" | "interview" | "offered" | "hired" | "rejected"
  >("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency">("all");
  const [experienceFilter, setExperienceFilter] = useState("");
  const [createdAtSort, setCreatedAtSort] = useState<CandidateCreatedAtSort>("newest");
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [bulkRecruiterId, setBulkRecruiterId] = useState("");
  const permissions = useAuthStore((state) => state.permissions);
  const searchParams = useSearchParams();
  const canCreate = hasPermission(permissions, CANDIDATES_CREATE_PERMISSION);
  const canReadCandidates = hasPermission(permissions, "candidates:read") || hasPermission(permissions, "candidates:read_own");
  const [showFilters, setShowFilters] = useState(false);
  const [submitModalCandidateId, setSubmitModalCandidateId] = useState<string | null>(null);
  const [submitModalJobId, setSubmitModalJobId] = useState("");
  const [submitLoading, setSubmitLoading] = useState(false);
  const [noteModalCandidateId, setNoteModalCandidateId] = useState<string | null>(null);
  const [noteInput, setNoteInput] = useState("");
  const [noteItems, setNoteItems] = useState<CandidateInteraction[]>([]);
  const [noteLoading, setNoteLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(
    () => readCachedCandidatesListPage()?.total_count ?? 0
  );
  const [loadingMore, setLoadingMore] = useState(false);
  const CANDIDATES_PAGE_SIZE = 50;



  function trackModuleEvent(eventName: string, payload?: Record<string, unknown>) {
    // Lightweight client telemetry hook; can be wired to analytics backend later.
    console.info("[candidate-module]", eventName, payload ?? {});
  }

  const listFilters = useCallback(
    (opts?: { query?: string; location?: string }) => ({
      query: opts?.query || undefined,
      location: opts?.location || undefined,
      status: statusFilter === "all" ? undefined : statusFilter,
      source: sourceFilter === "all" ? undefined : sourceFilter,
      min_years_experience: experienceFilter.trim() ? Number(experienceFilter) : undefined,
      job_id: selectedJobId || undefined,
    }),
    [experienceFilter, selectedJobId, sourceFilter, statusFilter]
  );

  const loadPipelinesForList = useCallback(async () => {
    try {
      const pipelineData = await getPipelines(100, 0);
      setPipelines(pipelineData);
    } catch {
      setPipelines([]);
    }
  }, []);

  const loadCandidates = useCallback(async (opts?: { query?: string; location?: string; silent?: boolean }) => {
    const filters = listFilters(opts);
    const canUseSessionCache = isDefaultCandidatesListFilters(filters);
    const hasSearch = Boolean(opts?.query?.trim() || opts?.location?.trim());

    if (!opts?.silent && hasSearch) {
      setSearching(true);
    }

    if (canUseSessionCache) {
      const cached = readCachedCandidatesListPage();
      if (cached) {
        setCandidates(cached.candidates);
        setTotalCount(cached.total_count);
        setListLoading(false);
      } else {
        setListLoading(true);
      }
    } else {
      setListLoading(true);
    }

    void loadPipelinesForList();

    try {
      const page = await getCandidatesPage(CANDIDATES_PAGE_SIZE, 0, filters);
      setCandidates(page.candidates);
      setTotalCount(page.total_count);
      if (canUseSessionCache) {
        writeCachedCandidatesListPage(page);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load candidates");
    } finally {
      setListLoading(false);
      setSearching(false);
    }
  }, [listFilters, loadPipelinesForList]);

  const loadCandidatesRef = useRef(loadCandidates);
  loadCandidatesRef.current = loadCandidates;

  const loadMoreCandidates = useCallback(async () => {
    if (loadingMore || candidates.length >= totalCount) {
      return;
    }
    setLoadingMore(true);
    try {
      const page = await getCandidatesPage(CANDIDATES_PAGE_SIZE, candidates.length, listFilters({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      }));
      setCandidates((prev) => {
        const seen = new Set(prev.map((item) => item.id));
        const merged = [...prev];
        for (const item of page.candidates) {
          if (!seen.has(item.id)) {
            seen.add(item.id);
            merged.push(item);
          }
        }
        return merged;
      });
      setTotalCount(page.total_count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load more candidates");
    } finally {
      setLoadingMore(false);
    }
  }, [candidates.length, listFilters, loadingMore, locationFilter, searchQuery, totalCount]);

  async function loadJobs() {
    setLoadingJobs(true);
    try {
      const data = await getJobsForSelect(100, 0);
      setJobs(data);
    } finally {
      setLoadingJobs(false);
    }
  }

  async function loadUsers() {
    try {
      const data = await getUsers();
      setUsers(data.filter((user) => user.role === "recruiter" || user.role === "admin"));
    } catch {
      // Dropdown gracefully degrades if users list is unavailable.
      setUsers([]);
    }
  }

  function requireJobSelection() {
    if (selectedJobId) {
      return true;
    }
    setError("Select a job before adding candidates.");
    return false;
  }

  function isDuplicateEmail(emailValue: string) {
    const normalized = emailValue.trim().toLowerCase();
    if (!normalized) return false;
    return candidates.some((candidate) => (candidate.email || "").trim().toLowerCase() === normalized);
  }

  async function attachCandidateToJob(candidateId: string) {
    if (!selectedJobId) return;
    await updateCandidate(candidateId, { job_id: selectedJobId });
  }

  async function saveSlotInteraction(candidateId: string) {
    const activeSlots = slots.filter((slot) => slot.startAt.trim() !== "");
    if (activeSlots.length === 0) return;
    const seen = new Set<string>();
    for (const slot of activeSlots) {
      const normalized = slot.startAt.trim();
      if (seen.has(normalized)) {
        throw new Error("Duplicate interview slot values are not allowed.");
      }
      seen.add(normalized);
      const ts = Date.parse(normalized);
      if (Number.isNaN(ts)) {
        throw new Error("Invalid slot date-time value.");
      }
      if (ts < Date.now() - 60_000) {
        throw new Error("Interview slot cannot be set in the past.");
      }
    }
    await addCandidateInteraction(candidateId, {
      interaction_type: "interview",
      title: "Slots (Recommended)",
      interaction_metadata: {
        timezone,
        slots: activeSlots.map((slot) => ({
          start_at: slot.startAt,
          note: slot.note.trim() || null,
        })),
      },
    });
  }

  useEffect(() => {
    if (!canReadCandidates) {
      setCandidates([]);
      setPipelines([]);
      setJobs([]);
      setUsers([]);
      setListLoading(false);
      setError("Forbidden: insufficient permissions.");
      return;
    }
    const jobIdFromQuery = searchParams.get("jobId");
    if (jobIdFromQuery) {
      setSelectedJobId(jobIdFromQuery);
    }
    void loadCandidatesRef.current();
    void loadJobs();
    void loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount / query change only; filter apply calls loadCandidates explicitly
  }, [canReadCandidates, searchParams]);

  const SEARCH_DEBOUNCE_MS = 300;

  useEffect(() => {
    if (!canReadCandidates) {
      return;
    }
    if (!searchDebounceBootstrappedRef.current) {
      searchDebounceBootstrappedRef.current = true;
      return;
    }
    const timer = window.setTimeout(() => {
      void loadCandidatesRef.current({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [canReadCandidates, searchQuery, locationFilter]);

  async function handleCreateCandidate() {
    if (!requireJobSelection()) return;
    if (!firstName.trim() || !lastName.trim()) {
      setError("First name and last name are required.");
      return;
    }
    if (isDuplicateEmail(email)) {
      setError("A candidate with this email already exists.");
      return;
    }
    setCreating(true);
    try {
      const created = await createCandidate({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        location: location.trim() || undefined,
        headline: candidateRole.trim() || undefined,
        years_experience: yearsExperience.trim() ? Number(yearsExperience.trim()) : undefined,
        summary: summary.trim() || undefined,
        stage: "applied",
        source: "manual",
        job_id: selectedJobId || undefined,
      });
      await attachCandidateToJob(created.id);
      await saveSlotInteraction(created.id);
      setCandidates((prev) => [created, ...prev]);
      trackModuleEvent("candidate_created_manual", { candidateId: created.id, jobId: selectedJobId });
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhone("");
      setLocation("");
      setCandidateRole("");
      setYearsExperience("");
      setSummary("");
      setSlots([{ startAt: "", note: "" }]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create candidate.");
    } finally {
      setCreating(false);
    }
  }

  async function handleUploadResume() {
    if (!requireJobSelection()) return;
    if (!resumeFile) {
      setError("Please choose a resume file.");
      return;
    }
    if (resumeFile.size > 10 * 1024 * 1024) {
      setError("File exceeds 10MB limit.");
      return;
    }
    setUploading(true);
    try {
      const payload = await uploadResumeForReview(resumeFile);
      setDraftCandidate({
        first_name: payload.draft.first_name,
        last_name: payload.draft.last_name,
        email: payload.draft.email ?? "",
        phone: payload.draft.phone ?? "",
        location: payload.draft.location ?? "",
        headline: payload.draft.headline ?? "",
        years_experience:
          payload.draft.years_experience === null || payload.draft.years_experience === undefined
            ? ""
            : String(payload.draft.years_experience),
        summary: payload.draft.summary ?? "",
        resume_s3_key: payload.draft.resume_s3_key,
        resume_file_name: payload.draft.resume_file_name,
      });
      setParseResult(payload.parse_result);
      trackModuleEvent("resume_parsed_for_review", { fileName: resumeFile.name, jobId: selectedJobId });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload and parse resume.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveReviewedCandidate() {
    if (!draftCandidate) return;
    if (!draftCandidate.first_name.trim() || !draftCandidate.last_name.trim()) {
      setError("First name and last name are required in parsed resume verification.");
      return;
    }
    if (isDuplicateEmail(draftCandidate.email)) {
      setError("A candidate with this email already exists.");
      return;
    }
    setSavingReview(true);
    try {
      const created = await createCandidate({
        first_name: draftCandidate.first_name.trim(),
        last_name: draftCandidate.last_name.trim(),
        email: draftCandidate.email.trim() || undefined,
        phone: draftCandidate.phone.trim() || undefined,
        location: draftCandidate.location.trim() || undefined,
        headline: draftCandidate.headline.trim() || undefined,
        years_experience: draftCandidate.years_experience.trim()
          ? Number(draftCandidate.years_experience.trim())
          : undefined,
        summary: draftCandidate.summary.trim() || undefined,
        source: "resume_upload",
        stage: "applied",
        job_id: selectedJobId || undefined,
        resume_s3_key: draftCandidate.resume_s3_key,
        resume_file_name: draftCandidate.resume_file_name,
        parse_confidence: parseResult?.parse_confidence ?? undefined,
        parsed_resume_data: parseResult?.parsed_resume_data,
      });
      await attachCandidateToJob(created.id);
      await saveSlotInteraction(created.id);
      setCandidates((prev) => [created, ...prev]);
      trackModuleEvent("candidate_created_resume", { candidateId: created.id, jobId: selectedJobId });
      setDraftCandidate(null);
      setParseResult(null);
      setResumeFile(null);
      setSlots([{ startAt: "", note: "" }]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save parsed candidate.");
    } finally {
      setSavingReview(false);
    }
  }

  async function handleCreateBulkUpload() {
    if (!requireJobSelection()) return;
    let files = csvResumeKeys
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (csvFile) {
      const text = await csvFile.text();
      const rows = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      const parsedFromFile = rows
        .map((line) => line.split(",")[0]?.trim())
        .filter((line): line is string => Boolean(line && line.length > 0));
      files = [...new Set([...parsedFromFile, ...files])];
    }
    if (files.length === 0) {
      setError("Add at least one resume key for CSV/XLS bulk upload.");
      return;
    }
    setBulkCreating(true);
    try {
      const job = await createBulkUploadJob({ files, source: "import" });
      setBulkJob(job);
      setViewImportedOnly(false);
      trackModuleEvent("bulk_upload_started", { itemCount: files.length, jobId: job.id });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create bulk upload job.");
    } finally {
      setBulkCreating(false);
    }
  }

  const refreshBulkStatus = useCallback(async () => {
    if (!bulkJob) return;
    setBulkPolling(true);
    try {
      const status = await getBulkUploadJobStatus(bulkJob.id);
      setBulkJob(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load bulk status.");
    } finally {
      setBulkPolling(false);
    }
  }, [bulkJob]);

  useEffect(() => {
    if (!bulkJob) return;
    if (bulkJob.status === "completed" || bulkJob.status === "failed") return;
    const timer = window.setInterval(() => {
      refreshBulkStatus();
    }, 6000);
    return () => window.clearInterval(timer);
  }, [bulkJob, refreshBulkStatus]);

  const bulkProgress = useMemo(() => {
    if (!bulkJob || bulkJob.total_items <= 0) return 0;
    return Math.min(100, Math.round((bulkJob.processed_items / bulkJob.total_items) * 100));
  }, [bulkJob]);

  const bulkStateLabel = useMemo(() => {
    if (!bulkJob) return null;
    if (bulkCreating) return "uploading";
    if (bulkJob.status === "pending" || bulkJob.status === "processing") return "processing";
    if (bulkJob.status === "completed") return "completed";
    return "completed";
  }, [bulkCreating, bulkJob]);

  const pipelineByCandidate = useMemo(() => {
    const map = new Map<string, Pipeline>();
    for (const item of pipelines) {
      if (selectedJobId && item.job_id !== selectedJobId) {
        continue;
      }
      const existing = map.get(item.candidate_id);
      if (!existing) {
        map.set(item.candidate_id, item);
        continue;
      }
      const existingUpdated = new Date(existing.updated_at).getTime();
      const nextUpdated = new Date(item.updated_at).getTime();
      if (nextUpdated > existingUpdated) {
        map.set(item.candidate_id, item);
      }
    }
    return map;
  }, [pipelines, selectedJobId]);

  const pipelineCountByCandidate = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of pipelines) {
      const prev = map.get(item.candidate_id) ?? 0;
      map.set(item.candidate_id, prev + 1);
    }
    return map;
  }, [pipelines]);

  function pipelineStageLabel(pipeline: Pipeline | undefined) {
    if (!pipeline) return "-";
    if (pipeline.stage === "offer") return "Offered";
    if (pipeline.stage === "placed") return "Hired";
    return pipeline.stage.charAt(0).toUpperCase() + pipeline.stage.slice(1);
  }

  function getCandidateSourceKey(candidate: Candidate): string {
    if (candidate.source === "import") return "bulk_upload";
    if (candidate.source) return candidate.source;
    if (candidate.source_type === "vendor") return "agency";
    if (candidate.source_type === "internal") return "manual";
    // Legacy rows can miss source metadata; treat as manual instead of blank.
    return "manual";
  }

  function getCandidateSourceLabel(candidate: Candidate): string {
    const key = getCandidateSourceKey(candidate);
    return key.replace(/_/g, " ");
  }

  const sortedCandidates = useMemo(() => {
    let data = viewImportedOnly 
      ? candidates.filter((candidate) => candidate.source === "bulk_upload" || candidate.source === "import") 
      : [...candidates];
    
    if (locationFilter.trim()) {
      const loc = locationFilter.trim().toLowerCase();
      data = data.filter((c) => (c.location || "").toLowerCase().includes(loc));
    }

    if (statusFilter !== "all") {
      data = data.filter((c) => (c.status ?? "active") === statusFilter);
    }

    if (sourceFilter !== "all") {
      data = data.filter((c) => getCandidateSourceKey(c) === sourceFilter);
    }

    if (experienceFilter.trim()) {
      const minYears = Number(experienceFilter.trim());
      if (!Number.isNaN(minYears)) {
        data = data.filter((c) => (c.years_experience ?? -1) >= minYears);
      }
    }

    if (stageFilter !== "all") {
      data = data.filter((c) => {
        const pipeline = pipelineByCandidate.get(c.id);
        if (!pipeline) return false;
        if (pipeline.stage === "offer") return stageFilter === "offered";
        if (pipeline.stage === "placed") return stageFilter === "hired";
        return pipeline.stage === stageFilter;
      });
    }

    const sort = createdAtSort === "oldest" ? "oldest" : "newest";
    data.sort((a, b) => compareCandidatesByCreatedAt(a, b, sort));
    return data;
  }, [
    candidates,
    createdAtSort,
    viewImportedOnly,
    locationFilter,
    statusFilter,
    sourceFilter,
    experienceFilter,
    pipelineByCandidate,
    jobs,
    stageFilter,
  ]);

  async function handleSearchApply() {
    await loadCandidates({
      query: searchQuery.trim() || undefined,
      location: locationFilter.trim() || undefined,
      silent: false,
    });
  }

  function handleResetFilters() {
    setSearchQuery("");
    setLocationFilter("");
    setStatusFilter("all");
    setStageFilter("all");
    setSourceFilter("all");
    setExperienceFilter("");
    setCreatedAtSort("newest");
    setSelectedJobId("");
    void loadCandidates();
  }

  function updateSlot(index: number, patch: Partial<SlotDraft>) {
    setSlots((prev) => prev.map((slot, i) => (i === index ? { ...slot, ...patch } : slot)));
  }

  function addSlotRow() {
    setSlots((prev) => [...prev, { startAt: "", note: "" }]);
  }

  function removeSlotRow(index: number) {
    setSlots((prev) => prev.filter((_, i) => i !== index));
  }

  const selectedJobTitle = jobs.find((job) => job.id === selectedJobId)?.title ?? "No job selected";

  async function openNotesModal(candidateId: string) {
    setNoteModalCandidateId(candidateId);
    setNoteInput("");
    setNoteLoading(true);
    try {
      const interactions = await getCandidateInteractions(candidateId, 100, 0);
      setNoteItems(interactions.filter((item) => item.interaction_type === "note"));
    } catch {
      setNoteItems([]);
    } finally {
      setNoteLoading(false);
    }
  }

  async function saveNote() {
    if (!noteModalCandidateId || !noteInput.trim()) return;
    setNoteSaving(true);
    try {
      await addCandidateInteraction(noteModalCandidateId, {
        interaction_type: "note",
        title: "Candidate note",
        body: noteInput.trim(),
        interaction_metadata: {
          candidate_id: noteModalCandidateId,
          text: noteInput.trim(),
          created_at: new Date().toISOString(),
        },
      });
      const interactions = await getCandidateInteractions(noteModalCandidateId, 100, 0);
      setNoteItems(interactions.filter((item) => item.interaction_type === "note"));
      setNoteInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add note.");
    } finally {
      setNoteSaving(false);
    }
  }

  async function submitCandidateToPipeline(candidateId: string, jobId: string) {
    const selectedJob = jobs.find((job) => job.id === jobId);
    if (selectedJob && selectedJob.status !== "open") {
      setError("This job is not open. Move it to Open before submitting candidates.");
      return;
    }
    const duplicate = pipelines.some((item) => item.candidate_id === candidateId && item.job_id === jobId);
    if (duplicate) {
      setError("Candidate is already submitted to this job.");
      return;
    }
    setSubmitLoading(true);
    try {
      console.info("[candidate-submit] payload", { candidateId, jobId });
      try {
        await submitCandidateToJob(jobId, candidateId);
      } catch (err) {
        // Mixed deployments can return 404 when the canonical submit path cannot resolve
        // candidate-management-origin candidate records. Fall back to assigning job_id.
        if (err instanceof ApiError && err.status === 404) {
          await updateCandidate(candidateId, { job_id: jobId });
        } else {
          throw err;
        }
      }

      setSubmitModalCandidateId(null);
      setSubmitModalJobId("");
      try {
        const pipelineData = await getPipelines(200, 0, jobId);
        console.info("[candidate-submit] pipeline refresh count (job filtered)", pipelineData.length);
        setPipelines(pipelineData);
      } catch {
        setPipelines([]);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          const detailValue =
            typeof err.detail === "string"
              ? err.detail
              : err.detail && typeof err.detail === "object" && "detail" in err.detail
                ? String((err.detail as { detail?: unknown }).detail ?? "")
                : "";
          if (detailValue === "JOB_NOT_OPEN") {
            setError("This job is not open. Move it to Open or On Hold before submitting candidates.");
          } else {
            setError("Candidate is already submitted to this job.");
            try {
              const pipelineData = await getPipelines(200, 0, jobId);
              setPipelines(pipelineData);
            } catch {
              // Keep the existing list if refresh fails.
            }
          }
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to submit candidate to job.");
      }
    } finally {
      setSubmitLoading(false);
    }
  }

  async function handleBulkArchive() {
    if (selectedCandidateIds.length === 0) return;
    setBulkActionLoading(true);
    try {
      const prevCandidates = candidates;
      setCandidates((prev) => prev.filter((candidate) => !selectedCandidateIds.includes(candidate.id)));
      await bulkDeleteCandidates({ candidate_ids: selectedCandidateIds });
      setSelectedCandidateIds([]);
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
    } catch (err) {
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
      setError(err instanceof Error ? err.message : "Unable to delete selected candidates.");
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function handleBulkUnarchive() {
    if (selectedCandidateIds.length === 0) return;
    setBulkActionLoading(true);
    try {
      setCandidates((prev) => prev.filter((candidate) => !selectedCandidateIds.includes(candidate.id)));
      await bulkUnarchiveCandidates({ candidate_ids: selectedCandidateIds });
      setSelectedCandidateIds([]);
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
    } catch (err) {
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
      setError(err instanceof Error ? err.message : "Unable to unarchive selected candidates.");
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function handleBulkHardDelete() {
    if (selectedCandidateIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to PERMANENTLY delete ${selectedCandidateIds.length} candidate(s)? This action cannot be undone.`)) {
      return;
    }
    setBulkActionLoading(true);
    try {
      setCandidates((prev) => prev.filter((candidate) => !selectedCandidateIds.includes(candidate.id)));
      await bulkHardDeleteCandidates({ candidate_ids: selectedCandidateIds });
      setSelectedCandidateIds([]);
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
    } catch (err) {
      await loadCandidates({
        query: searchQuery.trim() || undefined,
        location: locationFilter.trim() || undefined,
      });
      setError(err instanceof Error ? err.message : "Unable to permanently delete selected candidates.");
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function handleBulkAssignRecruiter() {
    if (selectedCandidateIds.length === 0) return;
    if (!bulkRecruiterId.trim()) {
      setError("Select recruiter for bulk assignment.");
      return;
    }
    setBulkActionLoading(true);
    const previous = candidates;
    try {
      setCandidates((prev) =>
        prev.map((candidate) =>
          selectedCandidateIds.includes(candidate.id) ? { ...candidate, recruiter_id: bulkRecruiterId.trim() } : candidate
        )
      );
      await bulkAssignRecruiter({
        candidate_ids: selectedCandidateIds,
        recruiter_id: bulkRecruiterId.trim(),
      });
      setSelectedCandidateIds([]);
      setBulkRecruiterId("");
    } catch (err) {
      setCandidates(previous);
      setError(err instanceof Error ? err.message : "Unable to assign recruiter.");
    } finally {
      setBulkActionLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Candidates</h1>
        </div>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-default">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[13px] font-semibold text-slate-600 group-hover:text-[#FF5A1F] transition-colors duration-300">Total Candidates</p>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-[32px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{candidates.length}</p>
          </div>
        </div>
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-default">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[13px] font-semibold text-slate-600 group-hover:text-[#FF5A1F] transition-colors duration-300">New Applicants</p>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-[32px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{pipelines.filter((item) => item.stage === "applied").length}</p>
          </div>
        </div>
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-default">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[13px] font-semibold text-slate-600 group-hover:text-[#FF5A1F] transition-colors duration-300">In Screening</p>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-[32px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{pipelines.filter((item) => item.stage === "screening").length}</p>
          </div>
        </div>
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white p-5 border border-slate-100/50 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-default">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[13px] font-semibold text-slate-600 group-hover:text-[#FF5A1F] transition-colors duration-300">Interview Stage</p>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-[32px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{pipelines.filter((item) => item.stage === "interview").length}</p>
          </div>
        </div>
      </div>

      <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white overflow-hidden border border-slate-100/50 mt-6">
        <div className="p-6 pb-4 flex flex-col md:flex-row items-center justify-between gap-4 border-b border-slate-100/80">
          <div className="flex flex-1 items-center gap-4 w-full">
            <div className="relative flex-1 max-w-[500px] group">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-[#FF5A1F] transition-colors" />
              <input
                className="w-full h-11 pl-11 pr-4 text-[14px] font-medium bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgba(0,0,0,0.02)] focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/15 focus:border-[#FF5A1F]/30 transition-all duration-200 placeholder:text-slate-400 text-slate-800"
                placeholder="Search candidates, location, role..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void handleSearchApply()}
                aria-busy={searching}
              />
              {searching ? (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-slate-400">
                  Searching…
                </span>
              ) : null}
            </div>
            <button 
              className={`flex items-center gap-2 px-4 h-11 rounded-2xl border transition-all text-[13px] font-semibold ${showFilters ? 'bg-slate-50 border-slate-300 text-slate-900 shadow-inner' : 'bg-white border-slate-200/80 text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-[0_2px_8px_rgba(0,0,0,0.02)]'}`}
              onClick={() => setShowFilters(!showFilters)}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 8.293A1 1 0 013 7.586V4z" />
              </svg>
              Filters
            </button>
            <div className="relative shrink-0">
              <label className="sr-only" htmlFor="candidate-created-at-sort">
                Sort candidates by creation date
              </label>
              <select
                id="candidate-created-at-sort"
                className="appearance-none flex items-center gap-2 pl-4 pr-9 h-11 rounded-2xl border border-slate-200/80 bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-[0_2px_8px_rgba(0,0,0,0.02)] transition-all text-[13px] font-semibold cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/15 focus:border-[#FF5A1F]/30"
                value={createdAtSort}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value === "newest" || value === "oldest") {
                    setCreatedAtSort(value);
                    return;
                  }
                  setCreatedAtSort("newest");
                }}
              >
                {CREATED_AT_SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    Sort: {option.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            </div>
          </div>
          {canCreate && (
            <Link href="/candidates/create">
              <button className="flex items-center gap-2 px-5 h-11 bg-[#FF5A1F] hover:bg-[#e04814] text-white rounded-2xl text-[13px] font-bold transition-colors shadow-sm">
                + Add Candidate
              </button>
            </Link>
          )}
        </div>

        <div className="p-0">

          {showFilters && (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 animate-in slide-in-from-top-2 duration-200">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 ml-1">Location</label>
                  <Input placeholder="City, Country..." value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 ml-1">Status</label>
                  <select
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm bg-white"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "archived" | "deleted")}
                  >
                    <option value="all">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="deleted">Archived</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 ml-1">Stage</label>
                  <select
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm bg-white"
                    value={stageFilter}
                    onChange={(e) =>
                      setStageFilter(
                        e.target.value as "all" | "applied" | "screening" | "interview" | "offered" | "hired" | "rejected"
                      )
                    }
                  >
                    <option value="all">All Stages</option>
                    <option value="applied">Applied</option>
                    <option value="screening">Screening</option>
                    <option value="interview">Interview</option>
                    <option value="offered">Offered</option>
                    <option value="hired">Hired</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 ml-1">Source</label>
                  <select
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm bg-white"
                    value={sourceFilter}
                    onChange={(e) => setSourceFilter(e.target.value as any)}
                  >
                    <option value="all">All Sources</option>
                    <option value="manual">Manual</option>
                    <option value="resume_upload">Resume Upload</option>
                    <option value="bulk_upload">Bulk Upload</option>
                    <option value="referral">Referral</option>
                    <option value="agency">Agency</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase text-slate-500 ml-1">Experience (Min Years)</label>
                  <Input
                    placeholder="e.g. 5"
                    type="number"
                    min={0}
                    value={experienceFilter}
                    onChange={(e) => setExperienceFilter(e.target.value)}
                  />
                </div>
                <div className="flex items-end gap-2 md:col-span-2">
                  <Button className="flex-1 bg-indigo-600 hover:bg-indigo-700" onClick={handleSearchApply}>Apply Filters</Button>
                  <Button variant="outline" onClick={handleResetFilters}>Reset</Button>
                </div>
              </div>
            </div>
          )}

          {selectedCandidateIds.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 py-2 px-4 bg-indigo-50/50 border-b border-indigo-100/50 animate-in fade-in slide-in-from-top-1 duration-200">
              <span className="text-[10px] font-bold uppercase text-indigo-600 mr-2">Bulk Actions: {selectedCandidateIds.length} selected</span>
              <Button
                variant="outline"
                className={`text-xs h-8 bg-white ${statusFilter === "deleted" ? "text-emerald-600 hover:text-emerald-700 border-emerald-100 hover:bg-emerald-50" : "text-red-600 hover:text-red-700 border-red-100 hover:bg-red-50"}`}
                disabled={bulkActionLoading}
                onClick={statusFilter === "deleted" ? handleBulkUnarchive : handleBulkArchive}
              >
                {statusFilter === "deleted" ? "Unarchive" : "Archive"}
              </Button>

              <Button
                variant="outline"
                className="text-xs h-8 bg-white text-red-700 hover:text-red-800 border-red-200 hover:bg-red-100"
                disabled={bulkActionLoading}
                onClick={handleBulkHardDelete}
              >
                Delete
              </Button>
            </div>
          )}
          <div className="overflow-x-auto min-h-[250px] pb-10">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100/80 bg-slate-50/50 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  <th className="px-3 py-2.5 font-bold">Candidate</th>
                  <th className="px-3 py-2.5 font-bold">Job</th>
                  <th className="px-3 py-2.5 font-bold">Stage</th>
                  <th className="px-3 py-2.5 font-bold">Source</th>
                  <th className="px-3 py-2.5 font-bold">Location</th>
                  <th className="px-3 py-2.5 font-bold">Role</th>
                  <th className="px-3 py-2.5 font-bold">Exp</th>
                  <th className="px-3 py-2.5 font-bold">Created</th>
                  <th className="px-3 py-2.5 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {listLoading && candidates.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-20 text-center text-slate-400">
                      <p className="text-lg font-medium">Loading candidates...</p>
                    </td>
                  </tr>
                ) : sortedCandidates.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-20 text-center text-slate-400">
                      <p className="text-lg font-medium">No candidates found</p>
                      <p className="text-sm">Try adjusting your filters or search query</p>
                    </td>
                  </tr>
                ) : (
                  sortedCandidates.map((candidate) => (
                    <tr 
                      key={candidate.id} 
                      className="border-b border-slate-100/60 hover:bg-slate-50/80 transition-colors text-xs group cursor-pointer"
                      onClick={() => router.push(`/candidates/${candidate.id}`)}
                    >
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold text-[10px] shrink-0 border border-indigo-100">
                          {candidate.first_name.charAt(0)}{candidate.last_name.charAt(0)}
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors truncate max-w-[140px]">{candidate.first_name} {candidate.last_name}</p>
                          <p className="text-[10px] text-slate-500 truncate max-w-[140px]">{candidate.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-slate-600">
                      <div className="truncate max-w-[120px]" title={(() => {
                        const pipeline = pipelineByCandidate.get(candidate.id);
                        const job = jobs.find((item) => item.id === pipeline?.job_id);
                        return job?.title ?? "-";
                      })()}>
                        {(() => {
                          const pipeline = pipelineByCandidate.get(candidate.id);
                          const job = jobs.find((item) => item.id === pipeline?.job_id);
                          return job?.title ?? "-";
                        })()}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700"
                        title={`Applied to ${pipelineCountByCandidate.get(candidate.id) ?? 0} jobs`}
                      >
                        {pipelineByCandidate.get(candidate.id) ? pipelineStageLabel(pipelineByCandidate.get(candidate.id)) : "Not submitted"}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider">
                        {getCandidateSourceLabel(candidate)}
                      </span>
                    </td>

                    <td className="px-3 py-3 text-slate-500">
                      <div className="truncate max-w-[120px]" title={candidate.location ?? ""}>
                        {candidate.location ?? "-"}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-slate-500">
                      <div className="max-w-[120px] truncate" title={candidate.role ?? ""}>
                        {candidate.role ?? "-"}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-slate-500 whitespace-nowrap">
                      {candidate.years_experience !== null && candidate.years_experience !== undefined
                        ? `${candidate.years_experience}y`
                        : "-"}
                    </td>
                    <td className="px-3 py-3 text-slate-500 whitespace-nowrap">
                      {new Date(candidate.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {canCreate ? (
                          <Button
                            variant="outline"
                            className="h-8 px-2 text-[11px]"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSubmitModalCandidateId(candidate.id);
                              setSubmitModalJobId(selectedJobId);
                            }}
                          >
                            Submit to Job
                          </Button>
                        ) : null}
                        
                        <div className="relative">
                          <Button
                            variant="ghost"
                            className="h-8 w-8 p-0 text-slate-400 hover:text-slate-900"
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenDropdownId(openDropdownId === candidate.id ? null : candidate.id);
                            }}
                          >
                            <MoreVertical className="h-4 w-4" />
                          </Button>

                          {openDropdownId === candidate.id && (
                            <>
                              <div
                                className="fixed inset-0 z-40"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenDropdownId(null);
                                }}
                              />
                              <div className="absolute right-0 mt-1 w-36 bg-white rounded-lg shadow-lg border border-slate-100 z-50 py-1 overflow-hidden">
                              {canCreate && (
                                <button
                                  className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-[#FF5A1F] transition-colors flex items-center gap-2"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenDropdownId(null);
                                    void openNotesModal(candidate.id);
                                  }}
                                >
                                  <FileText className="h-3.5 w-3.5" />
                                  Notes
                                </button>
                              )}
                              
                              {statusFilter === "deleted" ? (
                                <button
                                  className="w-full text-left px-3 py-2 text-xs text-emerald-600 hover:bg-emerald-50 transition-colors flex items-center gap-2"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    setOpenDropdownId(null);
                                    try {
                                      await bulkUnarchiveCandidates({ candidate_ids: [candidate.id] });
                                      setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
                                    } catch (err) {
                                      setError(err instanceof Error ? err.message : "Unable to unarchive candidate.");
                                    }
                                  }}
                                >
                                  <ArchiveRestore className="h-3.5 w-3.5" />
                                  Unarchive
                                </button>
                              ) : (
                                <button
                                  className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 hover:text-red-600 transition-colors flex items-center gap-2"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    setOpenDropdownId(null);
                                    try {
                                      setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
                                      await bulkDeleteCandidates({ candidate_ids: [candidate.id] });
                                    } catch (err) {
                                      setError(err instanceof Error ? err.message : "Unable to archive candidate.");
                                    }
                                  }}
                                >
                                  <ArchiveRestore className="h-3.5 w-3.5" />
                                  Archive
                                </button>
                              )}
                              
                              <button
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  setOpenDropdownId(null);
                                  if (!window.confirm("Are you sure you want to permanently delete this candidate?")) return;
                                  try {
                                    setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
                                    await bulkHardDeleteCandidates({ candidate_ids: [candidate.id] });
                                  } catch (err) {
                                    setError(err instanceof Error ? err.message : "Unable to delete candidate.");
                                  }
                                }}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                Delete
                              </button>
                            </div>
                            </>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {candidates.length < totalCount ? (
        <div className="flex items-center justify-center py-3">
          <Button variant="outline" disabled={loadingMore} onClick={() => void loadMoreCandidates()}>
            {loadingMore ? "Loading..." : `Load more (${candidates.length} of ${totalCount})`}
          </Button>
        </div>
      ) : null}
      {submitModalCandidateId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-4 shadow-xl">
            <h3 className="text-base font-semibold">Submit Candidate to Job</h3>
            <p className="mt-1 text-xs text-slate-500">Create a job-specific pipeline entry for this candidate.</p>
            <div className="mt-3 space-y-2">
              <label className="text-xs font-medium text-slate-500">Job</label>
              <select
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                value={submitModalJobId}
                onChange={(event) => setSubmitModalJobId(event.target.value)}
              >
                <option value="">Select job</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSubmitModalCandidateId(null)}>
                Cancel
              </Button>
              <Button
                disabled={submitLoading || !submitModalJobId}
                onClick={() => void submitCandidateToPipeline(submitModalCandidateId, submitModalJobId)}
              >
                {submitLoading ? "Submitting..." : "Submit"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {noteModalCandidateId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl">
            <h3 className="text-base font-semibold">Candidate Notes</h3>
            <div className="mt-3 flex gap-2">
              <Input value={noteInput} onChange={(event) => setNoteInput(event.target.value)} placeholder="Add note..." />
              <Button onClick={() => void saveNote()} disabled={noteSaving || !noteInput.trim()}>
                {noteSaving ? "Saving..." : "Save"}
              </Button>
            </div>
            <div className="mt-3 max-h-64 space-y-2 overflow-auto rounded border border-slate-200 p-2">
              {noteLoading ? <p className="text-xs text-slate-500">Loading notes...</p> : null}
              {!noteLoading && noteItems.length === 0 ? <p className="text-xs text-slate-500">No notes yet.</p> : null}
              {!noteLoading
                ? noteItems.map((item) => (
                    <div key={item.id} className="rounded border border-slate-100 p-2">
                      <p className="text-sm text-slate-800">{item.body ?? "-"}</p>
                      <p className="text-[11px] text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
                    </div>
                  ))
                : null}
            </div>
            <div className="mt-4 flex justify-end">
              <Button variant="outline" onClick={() => setNoteModalCandidateId(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
