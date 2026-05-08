"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import {
  addCandidateInteraction,
  bulkAssignRecruiter,
  bulkDeleteCandidates,
  bulkUpdateCandidateStage,
  createBulkUploadJob,
  createCandidate,
  getBulkUploadJobStatus,
  getCandidates,
  type CandidateManagementParseResult,
  type BulkUploadJobStatus,
  updateCandidate,
  uploadResumeForReview,
} from "@/lib/api/candidates";
import { getJobs, submitCandidateToJob } from "@/lib/api/jobs";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import type { Candidate, Job, OrganizationUser, Pipeline } from "@/lib/api/types";
import { getUsers } from "@/lib/api/users";
import { CANDIDATES_CREATE_PERMISSION, hasPermission } from "@/lib/rbac";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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
  const [activeStep, setActiveStep] = useState(1);
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
  const [bulkFiles, setBulkFiles] = useState<File[]>([]);
  const [bulkStatus, setBulkStatus] = useState<
    Array<{ name: string; status: "pending" | "parsing" | "success" | "duplicate" | "error"; error?: string }>
  >([]);
  const [bulkJob, setBulkJob] = useState<BulkUploadJobStatus | null>(null);
  const [draftCandidate, setDraftCandidate] = useState<CandidateDraft | null>(null);
  const [parseResult, setParseResult] = useState<CandidateManagementParseResult | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived" | "deleted">("all");
  const [stageFilter, setStageFilter] = useState<
    "all" | "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected"
  >("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency">("all");
  const [experienceFilter, setExperienceFilter] = useState("");
  const [sortBy, setSortBy] = useState<"updated_at" | "first_name" | "years_experience">("updated_at");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [bulkRecruiterId, setBulkRecruiterId] = useState("");
  const [bulkStage, setBulkStage] = useState<"applied" | "screening" | "interview" | "offer" | "placed" | "rejected">(
    "screening"
  );
  const permissions = useAuthStore((state) => state.permissions);
  const searchParams = useSearchParams();
  const canCreate = hasPermission(permissions, CANDIDATES_CREATE_PERMISSION);

  function trackModuleEvent(eventName: string, payload?: Record<string, unknown>) {
    // Lightweight client telemetry hook; can be wired to analytics backend later.
    console.info("[candidate-module]", eventName, payload ?? {});
  }

  const loadCandidates = useCallback(async (opts?: { query?: string; location?: string }) => {
    setLoading(true);
    try {
      const data = await getCandidates(50, 0, {
        query: opts?.query || undefined,
        location: opts?.location || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        stage: stageFilter === "all" ? undefined : stageFilter,
        source: sourceFilter === "all" ? undefined : sourceFilter,
        min_years_experience: experienceFilter.trim() ? Number(experienceFilter) : undefined,
        job_id: selectedJobId || undefined,
      });
      setCandidates(data);
      try {
        const pipelineData = await getPipelines(200, 0);
        setPipelines(pipelineData);
      } catch {
        // Candidate list remains usable even if pipeline summary cannot be loaded.
        setPipelines([]);
      }
      setError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load candidates");
      }
    } finally {
      setLoading(false);
    }
  }, [experienceFilter, selectedJobId, sourceFilter, stageFilter, statusFilter]);

  async function loadJobs() {
    setLoadingJobs(true);
    try {
      const data = await getJobs(200, 0);
      setJobs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load jobs");
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



  useEffect(() => {
    const jobIdFromQuery = searchParams.get("jobId");
    if (jobIdFromQuery) {
      setSelectedJobId(jobIdFromQuery);
    }
    void loadJobs();
    void loadUsers();
  }, [searchParams]);

  async function handleCreateCandidate() {
    if (!firstName.trim() || !lastName.trim()) {
      setError("First name and last name are required.");
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
      });
      setCandidates((prev) => [created, ...prev]);
      trackModuleEvent("candidate_created_manual", { candidateId: created.id });
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhone("");
      setLocation("");
      setCandidateRole("");
      setYearsExperience("");
      setSummary("");
      setError(null);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This candidate already exists in the system (Duplicate email or phone).");
      } else {
        setError(err instanceof Error ? err.message : "Unable to create candidate.");
      }
      return false;
    } finally {
      setCreating(false);
    }
  }

  async function handleUploadResume() {
    if (!resumeFile) {
      setError("Please choose a resume file.");
      return false;
    }
    if (resumeFile.size > 10 * 1024 * 1024) {
      setError("File exceeds 10MB limit.");
      return false;
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
      trackModuleEvent("resume_parsed_for_review", { fileName: resumeFile.name });
      setError(null);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload and parse resume.");
      return false;
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
        resume_s3_key: draftCandidate.resume_s3_key,
        resume_file_name: draftCandidate.resume_file_name,
        parse_confidence: parseResult?.parse_confidence ?? undefined,
        parsed_resume_data: parseResult?.parsed_resume_data,
      });
      setCandidates((prev) => [created, ...prev]);
      trackModuleEvent("candidate_created_resume", { candidateId: created.id });
      setDraftCandidate(null);
      setParseResult(null);
      setResumeFile(null);
      setError(null);
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("This candidate already exists in the system (Duplicate email or phone).");
      } else {
        setError(err instanceof Error ? err.message : "Unable to save parsed candidate.");
      }
      return false;
    } finally {
      setSavingReview(false);
    }
  }

  async function handleCreateBulkUpload() {
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

  async function handleBulkResumeUpload() {
    if (bulkFiles.length === 0) {
      setError("Please choose resume files.");
      return;
    }
    setBulkCreating(true);
    const newStatus = bulkFiles.map(f => ({ name: f.name, status: "pending" as const }));
    setBulkStatus(newStatus);

    for (let i = 0; i < bulkFiles.length; i++) {
      const file = bulkFiles[i];
      setBulkStatus(prev => prev.map((s, idx) => idx === i ? { ...s, status: "parsing" } : s));
      try {
        const payload = await uploadResumeForReview(file);
        const created = await createCandidate({
          first_name: payload.draft.first_name.trim() || "Unknown",
          last_name: payload.draft.last_name.trim() || "Candidate",
          email: payload.draft.email.trim() || undefined,
          phone: payload.draft.phone.trim() || undefined,
          location: payload.draft.location.trim() || undefined,
          headline: payload.draft.headline.trim() || undefined,
          years_experience: payload.draft.years_experience ?? undefined,
          summary: payload.draft.summary.trim() || undefined,
          source: "bulk_upload",
          stage: "applied",
          resume_s3_key: payload.draft.resume_s3_key,
          resume_file_name: payload.draft.resume_file_name,
          parse_confidence: payload.parse_result?.parse_confidence ?? undefined,
          parsed_resume_data: payload.parse_result?.parsed_resume_data,
        });
        setBulkStatus(prev => prev.map((s, idx) => idx === i ? { ...s, status: "success" } : s));
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          setBulkStatus((prev) => prev.map((s, idx) => (idx === i ? { ...s, status: "duplicate", error: "Already exists" } : s)));
          continue;
        }
        const msg = err instanceof Error ? err.message : String(err);
        setBulkStatus((prev) => prev.map((s, idx) => (idx === i ? { ...s, status: "error", error: msg } : s)));
      }
    }
    setBulkCreating(false);
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

  const sortedCandidates = useMemo(() => {
    const data = viewImportedOnly ? candidates.filter((candidate) => candidate.source === "bulk_upload" || candidate.source === "import") : [...candidates];
    data.sort((a, b) => {
      let result = 0;
      if (sortBy === "first_name") {
        result = `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`);
      } else if (sortBy === "years_experience") {
        result = (a.years_experience ?? -1) - (b.years_experience ?? -1);
      } else {
        result = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
      }
      return sortDirection === "asc" ? result : -result;
    });
    return data;
  }, [candidates, sortBy, sortDirection, viewImportedOnly]);

  async function handleSearchApply() {
    await loadCandidates({
      query: searchQuery.trim() || undefined,
      location: locationFilter.trim() || undefined,
    });
  }



  const selectedJobTitle = jobs.find((job) => job.id === selectedJobId)?.title ?? "No job selected";
  const pipelineByCandidate = useMemo(() => {
    const map = new Map<string, Pipeline>();
    for (const item of pipelines) {
      if (!map.has(item.candidate_id)) {
        map.set(item.candidate_id, item);
      }
    }
    return map;
  }, [pipelines]);

  async function handleBulkStageChange() {
    if (selectedCandidateIds.length === 0) return;
    setBulkActionLoading(true);
    try {
      const prevCandidates = candidates;
      const optimisticStage = (
        { offer: "offered", placed: "hired" } as Record<string, "offered" | "hired">
      )[bulkStage] ?? (bulkStage as "applied" | "screening" | "interview" | "rejected");
      setCandidates((prev) =>
        prev.map((candidate) =>
          selectedCandidateIds.includes(candidate.id) ? { ...candidate, stage: optimisticStage } : candidate
        )
      );
      await bulkUpdateCandidateStage({ candidate_ids: selectedCandidateIds, stage: optimisticStage });
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
      setError(err instanceof Error ? err.message : "Unable to apply bulk stage update.");
    } finally {
      setBulkActionLoading(false);
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

  const handleNext = () => setActiveStep((prev) => prev + 1);
  const handleBack = () => setActiveStep((prev) => Math.max(1, prev - 1));

  // Removed redundant monkey-patching of handlers

  const renderStepper = () => (
    <div className="mb-6 flex items-center justify-between border-b pb-4">
      {['Method', 'Upload', 'Review', 'Done'].map((step, idx) => (
        <div key={step} className={`flex items-center ${activeStep === idx + 1 ? 'text-blue-600 font-medium' : 'text-slate-400'}`}>
          <div className={`flex h-8 w-8 items-center justify-center rounded-full border-2 ${activeStep === idx + 1 ? 'border-blue-600 bg-blue-50' : 'border-slate-200'}`}>
            {idx + 1}
          </div>
          <span className="ml-2 text-sm">{step}</span>
          {idx < 3 && <div className="mx-4 h-px w-10 bg-slate-200" />}
        </div>
      ))}
    </div>
  );

  return (
    <section className="mx-auto max-w-4xl space-y-6 py-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Add Candidate</h1>
        <Link href="/candidates" className="text-sm text-slate-500 hover:text-slate-700">
          ← Back to List
        </Link>
      </div>

      {renderStepper()}

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {activeStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Select Method</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-4">
              <Button variant={addMode === "manual" ? "default" : "outline"} onClick={() => setAddMode("manual")} className="flex-1 min-w-[140px]">
                Add Manually
              </Button>
              <Button variant={addMode === "resume" ? "default" : "outline"} onClick={() => setAddMode("resume")} className="flex-1 min-w-[140px]">
                Upload Resume
              </Button>
              <Button variant={addMode === "csv" ? "default" : "outline"} onClick={() => setAddMode("csv")} className="flex-1 min-w-[140px]">
                Bulk AI Parse
              </Button>
            </div>
            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={handleBack}>Back</Button>
              <Button onClick={handleNext}>Next</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeStep === 2 && addMode === "manual" && (
        <Card>
          <CardHeader>
            <CardTitle>Manual Entry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
              <Input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
              <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
              <Input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <Input placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
              <Input placeholder="Role / Title" value={candidateRole} onChange={(e) => setCandidateRole(e.target.value)} />
              <Input placeholder="Years of experience" type="number" min={0} value={yearsExperience} onChange={(e) => setYearsExperience(e.target.value)} />
              <Input placeholder="Summary" value={summary} onChange={(e) => setSummary(e.target.value)} />
            </div>
            

            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={handleBack}>Back</Button>
              <Button onClick={async () => {
                const success = await handleCreateCandidate();
                if (success) setActiveStep(4);
              }} disabled={creating}>
                {creating ? "Saving..." : "Submit Candidate"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeStep === 2 && addMode === "resume" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload Resume</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input type="file" accept=".pdf,.docx" onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)} />
            <p className="text-xs text-slate-500">Accepted formats: PDF, DOCX. Max: 10MB.</p>
            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={handleBack}>Back</Button>
              <Button onClick={async () => {
                 const success = await handleUploadResume();
                 if (success) setActiveStep(3);
              }} disabled={uploading || !resumeFile}>
                {uploading ? "Parsing..." : "Upload & Parse"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeStep === 2 && addMode === "csv" && (
        <Card>
          <CardHeader>
            <CardTitle>Bulk Upload</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Select Resume Files (PDF/DOCX)</label>
                <Input 
                  type="file" 
                  multiple 
                  accept=".pdf,.docx" 
                  onChange={(e) => {
                    if (e.target.files) {
                      setBulkFiles(Array.from(e.target.files));
                    }
                  }} 
                />
              </div>

              {bulkStatus.length > 0 && (
                <div className="mt-4 space-y-2 max-h-60 overflow-y-auto rounded-md border p-3 bg-slate-50">
                  {bulkStatus.map((item, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs">
                      <span className="truncate max-w-[200px] font-medium">{item.name}</span>
                      <div className="flex items-center gap-2">
                        {item.status === "parsing" && <span className="text-blue-600 animate-pulse">Parsing...</span>}
                        {item.status === "success" && <span className="text-green-600">✓ Success</span>}
                        {item.status === "duplicate" && <span className="text-amber-600">↺ Already exists</span>}
                        {item.status === "error" && <span className="text-red-600" title={item.error}>✕ Failed</span>}
                        {item.status === "pending" && <span className="text-slate-400">Pending</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </div>

            {bulkJob && (
              <div className="mt-4 rounded bg-blue-50 p-4 text-sm border border-blue-100">
                <p className="font-medium text-blue-800">Job Status: {bulkStateLabel} ({bulkJob.processed_items}/{bulkJob.total_items})</p>
                <div className="mt-2 h-2 w-full bg-blue-200 rounded overflow-hidden">
                  <div className="h-2 bg-blue-600 transition-all duration-500" style={{width: `${bulkProgress}%`}} />
                </div>
              </div>
            )}
            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={handleBack}>Back</Button>
              <div className="space-x-2">
                {bulkFiles.length > 0 && (
                  <Button 
                    onClick={handleBulkResumeUpload} 
                    disabled={bulkCreating}
                    className="bg-indigo-600 hover:bg-indigo-700"
                  >
                    {bulkCreating ? "Processing Batch..." : `Parse ${bulkFiles.length} Resumes`}
                  </Button>
                )}
                {((bulkJob && bulkJob.status === 'completed') || (bulkStatus.length > 0 && !bulkCreating)) && (
                  <Button onClick={() => setActiveStep(4)}>Finish</Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeStep === 3 && draftCandidate && (
        <Card>
          <CardHeader>
            <CardTitle>Review Parsed Data</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Basic Information</p>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">First Name</label>
                    <Input value={draftCandidate.first_name} onChange={(e) => setDraftCandidate(p => p ? {...p, first_name: e.target.value} : p)} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">Last Name</label>
                    <Input value={draftCandidate.last_name} onChange={(e) => setDraftCandidate(p => p ? {...p, last_name: e.target.value} : p)} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">Email</label>
                    <Input value={draftCandidate.email} onChange={(e) => setDraftCandidate(p => p ? {...p, email: e.target.value} : p)} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">Phone</label>
                    <Input value={draftCandidate.phone} onChange={(e) => setDraftCandidate(p => p ? {...p, phone: e.target.value} : p)} />
                  </div>
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Professional Information</p>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">Location</label>
                    <Input value={draftCandidate.location} onChange={(e) => setDraftCandidate(p => p ? {...p, location: e.target.value} : p)} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-600">Headline / Current Role</label>
                    <Input value={draftCandidate.headline} onChange={(e) => setDraftCandidate(p => p ? {...p, headline: e.target.value} : p)} />
                  </div>
                </div>
              </div>
            </div>
            


            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={handleBack}>Back</Button>
              <Button onClick={async () => {
                const success = await handleSaveReviewedCandidate();
                if (success) setActiveStep(4);
              }} disabled={savingReview}>
                {savingReview ? "Saving..." : "Confirm & Save"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeStep === 4 && (
        <Card className="text-center py-12">
          <CardContent className="space-y-4">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-600 text-3xl">
              ✓
            </div>
            <h2 className="text-2xl font-semibold">Candidate Added!</h2>
            <p className="text-slate-500">The candidate has been successfully added to the job.</p>
            <div className="flex justify-center gap-4 pt-6">
              <Button variant="outline" onClick={() => {
                setActiveStep(1);
                setDraftCandidate(null);
                setFirstName("");
                setLastName("");
                setResumeFile(null);
                setCsvFile(null);
                setBulkJob(null);
              }}>
                Add Another
              </Button>
              <Link href="/candidates">
                <Button>Go to Candidate List</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
}