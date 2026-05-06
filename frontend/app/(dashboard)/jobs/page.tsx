"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { createJob, getJobs, updateJob, deleteJob, parseJD, type JobParseResult } from "@/lib/api/jobs";
import { JOBS_CREATE_PERMISSION, hasPermission } from "@/lib/rbac";
import { isAdminRole } from "@/lib/dashboard-nav";
import type { Job, JobStatus } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Briefcase, CircleDot, FileEdit, Shield, CheckCircle2 } from "lucide-react";

// ─── helpers ────────────────────────────────────────────────────────────────

function SkillTags({
  skills,
  onRemove,
  onAdd,
  placeholder,
}: {
  skills: string[];
  onRemove: (i: number) => void;
  onAdd: (s: string) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  function commit() {
    const v = draft.trim();
    if (v && !skills.includes(v)) onAdd(v);
    setDraft("");
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {skills.map((s, i) => (
          <span
            key={i}
            className="flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800"
          >
            {s}
            <button type="button" onClick={() => onRemove(i)} className="text-blue-500 hover:text-red-500">
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <Input
          className="h-7 text-xs"
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commit(); } }}
        />
        <Button type="button" variant="outline" className="h-7 px-2 text-xs" onClick={commit}>
          Add
        </Button>
      </div>
    </div>
  );
}

// ─── modal overlay ───────────────────────────────────────────────────────────

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-2xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-700 text-xl font-bold"
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  );
}

function ActionMenu({ onEdit, onDetails, onDelete }: { onEdit: () => void; onDetails: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);
  return (
    <div className="relative" ref={menuRef}>
      <button 
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(!open); }} 
        className="p-1.5 hover:bg-slate-100 rounded-md transition-colors"
      >
        <svg className="w-5 h-5 text-slate-400" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-32 bg-white border border-slate-100 rounded-md shadow-xl z-20 py-1 animate-in fade-in zoom-in-95 duration-100">
          <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(false); onDetails(); }} className="w-full text-left px-4 py-2 text-xs hover:bg-slate-50 font-medium text-slate-700">View Details</button>
          <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(false); onEdit(); }} className="w-full text-left px-4 py-2 text-xs hover:bg-slate-50 font-medium text-indigo-600">Edit Job</button>
          <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(false); onDelete(); }} className="w-full text-left px-4 py-2 text-xs hover:bg-slate-50 font-medium text-red-600">Delete Job</button>
        </div>
      )}
    </div>
  );
}

// ─── JD input modal (paste / upload) ────────────────────────────────────────

function JDInputModal({
  onClose,
  onParsed,
}: {
  onClose: () => void;
  onParsed: (result: JobParseResult) => void;
}) {
  const [tab, setTab] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseStep, setParseStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const PARSE_STEPS = ["Parsing JD...", "Extracting skills...", "Structuring data..."];

  useEffect(() => {
    if (!parsing) return;
    const interval = setInterval(() => {
      setParseStep((prev) => (prev + 1) % PARSE_STEPS.length);
    }, 1500);
    return () => clearInterval(interval);
  }, [parsing]);

  async function handleParse() {
    setError(null);
    if (tab === "paste" && !text.trim()) { setError("Paste a job description first."); return; }
    if (tab === "upload" && !file) { setError("Select a PDF file first."); return; }
    try {
      setParsing(true);
      const result = tab === "paste"
        ? await parseJD({ type: "text", text })
        : await parseJD({ type: "file", file: file! });
      onParsed({
        ...result,
        raw_jd_text: tab === "paste" ? text : undefined,
        parsing_source: tab === "paste" ? "text" : "pdf",
        parsing_status: "success",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Parsing failed. Try again.");
    } finally {
      setParsing(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <div className="p-6">
        <h2 className="text-xl font-semibold mb-1">Import from Job Description</h2>
        <p className="text-sm text-slate-500 mb-4">Paste or upload a JD — AI will extract all fields automatically.</p>

        {/* tabs */}
        <div className="flex border-b mb-4">
          {(["paste", "upload"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError(null); }}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t === "paste" ? "📋 Paste JD" : "📄 Upload PDF"}
            </button>
          ))}
        </div>

        {tab === "paste" ? (
          <textarea
            className="w-full h-64 rounded-md border border-slate-200 p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="Paste the full job description here…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        ) : (
          <div
            onClick={() => fileRef.current?.click()}
            className="flex h-40 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 text-slate-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
          >
            <span className="text-3xl">📂</span>
            <p className="mt-2 text-sm">{file ? file.name : "Click to select a PDF"}</p>
            <p className="text-xs mt-1">Only .pdf files are accepted</p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center justify-between bg-red-50 p-3 rounded-md border border-red-200">
            <p className="text-sm text-red-600">{error}</p>
            <Button variant="outline" onClick={handleParse} className="text-red-700 border-red-200 hover:bg-red-100">
              Retry
            </Button>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <Button onClick={handleParse} disabled={parsing}>
            {parsing ? PARSE_STEPS[parseStep] : "Parse JD →"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ─── preview / confirm modal ─────────────────────────────────────────────────

function JDPreviewModal({
  initial,
  clientId,
  onBack,
  onClose,
  onCreated,
}: {
  initial: JobParseResult;
  clientId: string;
  onBack: () => void;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState(initial.title ?? "");
  const [location, setLocation] = useState(initial.location ?? "");
  const [employmentType, setEmploymentType] = useState(initial.employment_type ?? "");
  const [expMin, setExpMin] = useState(initial.experience_min_years !== null ? String(initial.experience_min_years) : "");
  const [expMax, setExpMax] = useState(initial.experience_max_years !== null ? String(initial.experience_max_years) : "");
  const [salaryMin, setSalaryMin] = useState(initial.salary_min !== null ? String(initial.salary_min) : "");
  const [salaryMax, setSalaryMax] = useState(initial.salary_max !== null ? String(initial.salary_max) : "");
  const [salaryCurrency, setSalaryCurrency] = useState(initial.salary_currency ?? "USD");
  const [urgency, setUrgency] = useState(initial.urgency ?? "normal");
  const [description, setDescription] = useState(initial.description ?? "");
  const [requiredSkills, setRequiredSkills] = useState<string[]>(initial.required_skills ?? []);
  const [preferredSkills, setPreferredSkills] = useState<string[]>(initial.preferred_skills ?? []);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!title.trim()) { setError("Title is required."); return; }
    setError(null);
    try {
      setCreating(true);
      await createJob({
        client_id: clientId,
        title: title.trim(),
        description: description.trim() || null,
        status: "open",
        location: location.trim() || undefined,
        salary_min: salaryMin ? Number(salaryMin) : null,
        salary_max: salaryMax ? Number(salaryMax) : null,
        salary_currency: salaryCurrency,
        experience_min_years: expMin ? Number(expMin) : null,
        experience_max_years: expMax ? Number(expMax) : null,
        employment_type: employmentType || null,
        urgency: urgency || "normal",
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        raw_jd_text: initial.raw_jd_text,
        parsing_source: initial.parsing_source,
        parsing_status: initial.parsing_status,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create job.");
    } finally {
      setCreating(false);
    }
  }

  const urgencyColors: Record<string, string> = {
    normal: "bg-slate-100 text-slate-700",
    high: "bg-orange-100 text-orange-700",
    critical: "bg-red-100 text-red-700",
  };

  return (
    <Modal onClose={onClose}>
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Review Parsed Job</h2>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${urgencyColors[urgency] ?? urgencyColors.normal}`}>
            {urgency}
          </span>
        </div>
        <p className="text-sm text-slate-500">Review and edit any field before saving.</p>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 text-sm">
          <div className="md:col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Title *</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Job title" />
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Location</label>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Remote, Bangalore" />
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Employment Type</label>
            <select
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={employmentType}
              onChange={(e) => setEmploymentType(e.target.value)}
            >
              <option value="">(None)</option>
              <option value="full_time">Full Time</option>
              <option value="part_time">Part Time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Experience (years)</label>
            <div className="flex gap-2">
              <Input type="number" placeholder="Min" value={expMin} onChange={(e) => setExpMin(e.target.value)} />
              <Input type="number" placeholder="Max" value={expMax} onChange={(e) => setExpMax(e.target.value)} />
            </div>
          </div>


          <div>
            <label className="block text-xs text-slate-500 mb-1">Urgency</label>
            <select
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={urgency}
              onChange={(e) => setUrgency(e.target.value)}
            >
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Description</label>
            <textarea
              className="w-full h-32 rounded-md border border-slate-200 p-2 text-sm resize-none"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Required Skills</label>
            <SkillTags
              skills={requiredSkills}
              onRemove={(i) => setRequiredSkills((prev) => prev.filter((_, idx) => idx !== i))}
              onAdd={(s) => setRequiredSkills((prev) => [...prev, s])}
              placeholder="Add required skill…"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Preferred Skills</label>
            <SkillTags
              skills={preferredSkills}
              onRemove={(i) => setPreferredSkills((prev) => prev.filter((_, idx) => idx !== i))}
              onAdd={(s) => setPreferredSkills((prev) => [...prev, s])}
              placeholder="Add preferred skill…"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-between pt-2">
          <Button variant="outline" onClick={onBack}>← Back</Button>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Creating…" : "Create Job ✓"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "open" | "draft" | "closed">("all");
  const permissions = useAuthStore((state) => state.permissions);
  const role = useAuthStore((state) => state.role);
  const canCreateJobs = hasPermission(permissions, JOBS_CREATE_PERMISSION) || isAdminRole(role);

  // regular create form
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [clientId, setClientId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState<JobStatus>("open");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [preferredSkills, setPreferredSkills] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [salaryCurrency, setSalaryCurrency] = useState("USD");
  const [expMin, setExpMin] = useState("");
  const [expMax, setExpMax] = useState("");
  const [employmentType, setEmploymentType] = useState("");

  // Edit form state
  const [showEdit, setShowEdit] = useState(false);
  const [editingJobId, setEditingJobId] = useState<string | null>(null);
  
  // Import from JD flow state
  const [showClientPrompt, setShowClientPrompt] = useState(false);
  const [showJDInput, setShowJDInput] = useState(false);
  const [jdClientId, setJdClientId] = useState("");
  const [parsedResult, setParsedResult] = useState<JobParseResult | null>(null);

  async function refreshJobs() {
    const data = await getJobs(50, 0);
    setJobs(data);
  }

  async function handleDeleteJob(jobId: string) {
    if (!window.confirm("Are you sure you want to delete this job? This action cannot be undone.")) return;
    try {
      await deleteJob(jobId);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete job.");
    }
  }

  useEffect(() => {
    void refreshJobs();
    const interval = window.setInterval(() => {
      void refreshJobs();
    }, 30000);
    return () => window.clearInterval(interval);
  }, []);

  function handleImportClick() {
    // Ask for client ID before opening the JD input modal
    setShowClientPrompt(true);
  }

  function resetForm() {
    setTitle(""); setDescription(""); setLocation(""); setClientId("");
    setRequiredSkills(""); setPreferredSkills(""); setSalaryMin(""); setSalaryMax("");
    setExpMin(""); setExpMax(""); setEmploymentType("");
    setStatus("open");
  }

  function openEdit(job: Job) {
    setTitle(job.title || "");
    setDescription(job.description || "");
    setLocation(job.location || "");
    setClientId(job.client_id || "");
    setStatus(job.status || "open");
    setRequiredSkills(job.required_skills?.join(", ") || "");
    setPreferredSkills(job.preferred_skills?.join(", ") || "");
    setSalaryMin(job.salary_min?.toString() || "");
    setSalaryMax(job.salary_max?.toString() || "");
    setSalaryCurrency(job.salary_currency || "USD");
    setExpMin(job.experience_min_years?.toString() || "");
    setExpMax(job.experience_max_years?.toString() || "");
    setEmploymentType(job.employment_type || "");
    
    setEditingJobId(job.id);
    setShowEdit(true);
  }

  function getStatusBadgeClass(jobStatus: JobStatus) {
    if (jobStatus === "open") return "bg-green-100 text-green-700";
    if (jobStatus === "draft") return "bg-gray-100 text-gray-600";
    if (jobStatus === "cancelled" || jobStatus === "filled") return "bg-red-100 text-red-600";
    return "bg-slate-100 text-slate-600";
  }

  function getStatusLabel(jobStatus: JobStatus) {
    if (jobStatus === "cancelled" || jobStatus === "filled") return "Closed";
    return jobStatus.replace("_", " ");
  }

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch = job.title.toLowerCase().includes(searchQuery.toLowerCase().trim());
    if (!matchesSearch) return false;
    if (statusFilter === "all") return true;
    if (statusFilter === "closed") return job.status === "cancelled" || job.status === "filled";
    return job.status === statusFilter;
  });

  return (
    <section className="relative space-y-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Jobs</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="h-8 px-3 text-xs" onClick={() => void refreshJobs()}>
            Refresh
          </Button>
        {canCreateJobs ? (
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleImportClick}>
              ✨ Import from JD
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              + Create Job
            </Button>
          </div>
        ) : null}
        </div>
      </div>

      {error && !showCreate ? <p className="text-sm text-red-600">{error}</p> : null}

      {/* ── KPI Strip ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card className="cursor-pointer border-slate-200 shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-indigo-50 rounded-xl text-indigo-500">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Total Jobs</p>
              <h3 className="text-xl font-bold text-slate-900">{jobs.length}</h3>
              <p className="text-[10px] text-emerald-600 font-medium mt-0.5">All time</p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer border-slate-200 shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-emerald-50 rounded-xl text-emerald-500">
              <CircleDot className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Open Jobs</p>
              <h3 className="text-xl font-bold text-slate-900">{jobs.filter(j => j.status === "open").length}</h3>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                {jobs.length === 0 ? "0.0" : ((jobs.filter(j => j.status === "open").length / jobs.length) * 100).toFixed(1)}% of total
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer border-slate-200 shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-orange-50 rounded-xl text-orange-500">
              <FileEdit className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Draft Jobs</p>
              <h3 className="text-xl font-bold text-slate-900">{jobs.filter(j => j.status === "draft").length}</h3>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                {jobs.length === 0 ? "0.0" : ((jobs.filter(j => j.status === "draft").length / jobs.length) * 100).toFixed(1)}% of total
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer border-slate-200 shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-50 rounded-xl text-blue-500">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">On Hold</p>
              <h3 className="text-xl font-bold text-slate-900">{jobs.filter(j => j.status === "on_hold").length}</h3>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                {jobs.length === 0 ? "0.0" : ((jobs.filter(j => j.status === "on_hold").length / jobs.length) * 100).toFixed(1)}% of total
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer border-slate-200 shadow-sm transition-shadow hover:shadow-md">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-purple-50 rounded-xl text-purple-500">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Closed</p>
              <h3 className="text-xl font-bold text-slate-900">{jobs.filter(j => j.status === "cancelled" || j.status === "filled").length}</h3>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">
                {jobs.length === 0 ? "0.0" : ((jobs.filter(j => j.status === "cancelled" || j.status === "filled").length / jobs.length) * 100).toFixed(1)}% of total
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Job list ─────────────────────────────────────────────────── */}
      <Card className="rounded-xl border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle>Job List</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <input
              type="text"
              placeholder="Search jobs..."
              className="w-full rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200 md:w-72"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
            <div className="flex items-center gap-2">
              {(["all", "open", "draft", "closed"] as const).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setStatusFilter(filter)}
                  className={`cursor-pointer rounded-full px-3 py-1 text-sm transition ${
                    statusFilter === filter ? "bg-slate-300 text-slate-800" : "bg-slate-100 hover:bg-slate-200"
                  }`}
                >
                  {filter === "all" ? "All" : filter === "closed" ? "Closed" : filter.charAt(0).toUpperCase() + filter.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredJobs.map((job) => (
            <div
              key={job.id}
              className="group rounded-xl bg-white p-4 shadow-sm transition-all duration-150 hover:scale-[1.01] hover:shadow-md"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-2">
                  <p className="truncate text-base font-semibold text-slate-900">{job.title}</p>
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${getStatusBadgeClass(job.status)}`}>
                    {getStatusLabel(job.status)}
                  </span>
                </div>
              </div>

              <div className="mb-4 flex items-center gap-3 text-sm text-slate-500">
                {job.location ? <span>📍 {job.location}</span> : <span>📍 Location TBD</span>}
                {(job.experience_min_years !== null || job.experience_max_years !== null) ? (
                  <span>🎓 {job.experience_min_years ?? 0}-{job.experience_max_years ?? "+"} yrs</span>
                ) : (
                  <span>🎓 Experience TBD</span>
                )}
              </div>

              <div className="pt-1">
                <Link className="text-sm font-medium text-blue-600 hover:underline" href={`/jobs/${job.id}`}>
                  View →
                </Link>
              </div>
            </div>
          ))}
          {!filteredJobs.length ? (
            <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500 md:col-span-2 xl:col-span-3">
              No jobs found for the current search/filter.
            </div>
          ) : null}
          </div>
        </CardContent>
      </Card>

      {/* ── Create Job Slide-In Panel ─────────────────────────────────── */}
      {showCreate ? (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => { setShowCreate(false); resetForm(); setError(null); }} />
          <div className="relative w-full max-w-[480px] bg-white shadow-2xl h-full flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between p-6 border-b shrink-0">
              <h2 className="text-xl font-semibold text-slate-800">Create Job</h2>
              <button onClick={() => { setShowCreate(false); resetForm(); setError(null); }} className="text-slate-400 hover:text-slate-600 text-2xl font-bold p-1">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-6 text-sm">
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Client ID (UUID) *</label>
                  <Input value={clientId} onChange={(e) => setClientId(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Title *</label>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
                  <select className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value as JobStatus)}>
                    <option value="draft">Draft</option><option value="open">Open</option><option value="on_hold">On Hold</option><option value="cancelled">Cancelled</option><option value="filled">Filled</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
                  <textarea className="w-full h-32 rounded-md border border-slate-200 p-2 text-sm resize-none" value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Location</label>
                  <Input value={location} onChange={(e) => setLocation(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div><label className="block text-xs font-medium text-slate-500 mb-1">Min Exp</label><Input type="number" value={expMin} onChange={(e) => setExpMin(e.target.value)} /></div>
                  <div><label className="block text-xs font-medium text-slate-500 mb-1">Max Exp</label><Input type="number" value={expMax} onChange={(e) => setExpMax(e.target.value)} /></div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Required Skills (comma/newline)</label>
                  <textarea className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none" value={requiredSkills} onChange={(e) => setRequiredSkills(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Preferred Skills (comma/newline)</label>
                  <textarea className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none" value={preferredSkills} onChange={(e) => setPreferredSkills(e.target.value)} />
                </div>
              </div>
              {error && <p className="text-sm font-medium text-red-600 bg-red-50 p-3 rounded-md border border-red-100">{error}</p>}
            </div>
            <div className="p-6 border-t bg-slate-50 shrink-0">
              <Button className="w-full py-6 text-lg bg-indigo-600 hover:bg-indigo-700" disabled={creating} onClick={async () => {
                if (!title.trim() || !clientId.trim()) {
                  setError("Title and Client ID are required.");
                  return;
                }
                try {
                  setCreating(true);
                  const req = requiredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
                  const pref = preferredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
                  await createJob({
                    client_id: clientId.trim(),
                    title: title.trim(),
                    description: description.trim() || null,
                    status,
                    location: location.trim() || undefined,
                    experience_min_years: expMin ? Number(expMin) : null,
                    experience_max_years: expMax ? Number(expMax) : null,
                    required_skills: req,
                    preferred_skills: pref,
                  });
                  setShowCreate(false); resetForm(); await refreshJobs();
                } catch (err) { setError(err instanceof ApiError ? err.message : "Unable to create job."); } finally { setCreating(false); }
              }}>{creating ? "Creating..." : "Create Job"}</Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── Edit Job Slide-In Panel ─────────────────────────────────── */}
      {showEdit ? (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => { setShowEdit(false); resetForm(); setError(null); }} />
          <div className="relative w-full max-w-[480px] bg-white shadow-2xl h-full flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between p-6 border-b shrink-0">
              <h2 className="text-xl font-semibold text-slate-800">Edit Job</h2>
              <button onClick={() => { setShowEdit(false); resetForm(); setError(null); }} className="text-slate-400 hover:text-slate-600 text-2xl font-bold p-1">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-6 text-sm">
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Title *</label>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
                  <select className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value as JobStatus)}>
                    <option value="draft">Draft</option><option value="open">Open</option><option value="on_hold">On Hold</option><option value="cancelled">Cancelled</option><option value="filled">Filled</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
                  <textarea className="w-full h-32 rounded-md border border-slate-200 p-2 text-sm resize-none" value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Location</label>
                  <Input value={location} onChange={(e) => setLocation(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div><label className="block text-xs font-medium text-slate-500 mb-1">Min Exp</label><Input type="number" value={expMin} onChange={(e) => setExpMin(e.target.value)} /></div>
                  <div><label className="block text-xs font-medium text-slate-500 mb-1">Max Exp</label><Input type="number" value={expMax} onChange={(e) => setExpMax(e.target.value)} /></div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Required Skills (comma/newline)</label>
                  <textarea className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none" value={requiredSkills} onChange={(e) => setRequiredSkills(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Preferred Skills (comma/newline)</label>
                  <textarea className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none" value={preferredSkills} onChange={(e) => setPreferredSkills(e.target.value)} />
                </div>
              </div>
              {error && <p className="text-sm font-medium text-red-600 bg-red-50 p-3 rounded-md border border-red-100">{error}</p>}
            </div>
            <div className="p-6 border-t bg-slate-50 shrink-0">
              <Button className="w-full py-6 text-lg bg-indigo-600 hover:bg-indigo-700" disabled={creating} onClick={async () => {
                if (!title.trim() || !editingJobId) return;
                try {
                  setCreating(true);
                  const req = requiredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
                  const pref = preferredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
                  await updateJob(editingJobId, {
                    title: title.trim(),
                    description: description.trim() || null,
                    status,
                    location: location.trim() || undefined,
                    experience_min_years: expMin ? Number(expMin) : undefined,
                    experience_max_years: expMax ? Number(expMax) : undefined,
                    required_skills: req.length ? req : undefined,
                    preferred_skills: pref.length ? pref : undefined,
                  });
                  setShowEdit(false); resetForm(); await refreshJobs();
                } catch (err) { setError("Unable to update job."); } finally { setCreating(false); }
              }}>{creating ? "Saving..." : "Save Changes"}</Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* ── Client ID prompt before JD import ───────────────────────── */}
      {showClientPrompt ? (
        <Modal onClose={() => setShowClientPrompt(false)}>
          <div className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Enter Client ID</h2>
            <p className="text-sm text-slate-500">This is required to link the job to a client after parsing.</p>
            <datalist id="mock-clients-prompt">
              <option value="00000000-0000-0000-0000-000000000000">Default Client</option>
              <option value="11111111-1111-1111-1111-111111111111">Acme Corp</option>
              <option value="22222222-2222-2222-2222-222222222222">Globex</option>
            </datalist>
            <Input
              placeholder="Client ID (UUID)"
              list="mock-clients-prompt"
              value={jdClientId}
              onChange={(e) => setJdClientId(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowClientPrompt(false)}>Cancel</Button>
              <Button
                onClick={() => {
                  if (!jdClientId.trim()) return;
                  setShowClientPrompt(false);
                  setShowJDInput(true);
                }}
              >
                Continue →
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}

      {/* ── JD Input modal ───────────────────────────────────────────── */}
      {showJDInput ? (
        <JDInputModal
          onClose={() => setShowJDInput(false)}
          onParsed={(result) => {
            setParsedResult(result);
            setShowJDInput(false);
          }}
        />
      ) : null}

      {/* ── Preview / confirm modal ──────────────────────────────────── */}
      {parsedResult ? (
        <JDPreviewModal
          initial={parsedResult}
          clientId={jdClientId}
          onBack={() => {
            setParsedResult(null);
            setShowJDInput(true);
          }}
          onClose={() => { setParsedResult(null); setJdClientId(""); }}
          onCreated={async () => {
            setParsedResult(null);
            setJdClientId("");
            await refreshJobs();
          }}
        />
      ) : null}
    </section>
  );
}
