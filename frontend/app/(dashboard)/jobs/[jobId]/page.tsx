import { redirect } from "next/navigation";

<<<<<<< HEAD
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getJobById, getJobSubmissions, updateJob } from "@/lib/api/jobs";
import { getPipelines } from "@/lib/api/pipeline";
import type { Job, JobSubmission, JobStatus, Pipeline } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Clipboard, 
  Search,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Zap,
  ArrowLeft,
  Users,
  Target,
  Calendar,
  Sparkles,
  ArrowRight,
  X,
  FileText,
  Layers,
  Briefcase,
  Edit3,
  MoreVertical,
  MapPin,
  Banknote,
  Clock
} from "lucide-react";

// ─── components ─────────────────────────────────────────────────────────────

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${className || ""}`}>
      {children}
    </span>
  );
}

// ─── formatting helpers ─────────────────────────────────────────────────────

const formatSalary = (amt: number | null, currency: string | null) => {
  if (amt === null) return "Not specified";
  if (currency === "INR" && amt >= 100000) {
    const lakhs = amt / 100000;
    return `₹${lakhs.toFixed(amt % 100000 === 0 ? 0 : 1)}L`;
  }
  return `${amt.toLocaleString()} ${currency || "USD"}`;
};

const formatDate = (d: string | null | undefined) => {
  if (!d) return "Not available";
  const date = new Date(d);
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
};

// ─── components ─────────────────────────────────────────────────────────────

function ActionMenu({ onEdit }: { onEdit: () => void }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={menuRef}>
      <button 
        onClick={() => setOpen(!open)}
        className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
        aria-label="Job actions"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <MoreVertical className="w-5 h-5" />
      </button>
      {open && (
        <div 
          className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50 animate-in fade-in zoom-in-95 duration-100"
          role="menu"
        >
          <button 
            onClick={() => { setOpen(false); onEdit(); }}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-indigo-600 transition-colors flex items-center gap-2"
            role="menuitem"
          >
            <Edit3 className="w-4 h-4" /> Edit Job
          </button>
        </div>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [submissions, setSubmissions] = useState<JobSubmission[]>([]);
  const [submissionsTotal, setSubmissionsTotal] = useState(0);
  const [submissionsError, setSubmissionsError] = useState<string | null>(null);
  const [submissionsLoading, setSubmissionsLoading] = useState(false);
  const [bannerVisible, setBannerVisible] = useState(true);

  const [activeTab, setActiveTab] = useState<"overview" | "raw_jd">("overview");
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Edit Job State
  const [showEdit, setShowEdit] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editStatus, setEditStatus] = useState<JobStatus>("open");
  const [editRequiredSkills, setEditRequiredSkills] = useState("");
  const [editPreferredSkills, setEditPreferredSkills] = useState("");
  const [editSalaryMin, setEditSalaryMin] = useState("");
  const [editSalaryMax, setEditSalaryMax] = useState("");
  const [editSalaryCurrency, setEditSalaryCurrency] = useState("USD");
  const [editExpMin, setEditExpMin] = useState("");
  const [editExpMax, setEditExpMax] = useState("");
  const [editEmploymentType, setEditEmploymentType] = useState("");

  function openEditPanel() {
    if (!job) return;
    setEditTitle(job.title || "");
    setEditDescription(job.description || "");
    setEditLocation(job.location || "");
    setEditStatus(job.status || "open");
    setEditRequiredSkills(job.required_skills?.join(", ") || "");
    setEditPreferredSkills(job.preferred_skills?.join(", ") || "");
    setEditSalaryMin(job.salary_min?.toString() || "");
    setEditSalaryMax(job.salary_max?.toString() || "");
    setEditSalaryCurrency(job.salary_currency || "USD");
    setEditExpMin(job.experience_min_years?.toString() || "");
    setEditExpMax(job.experience_max_years?.toString() || "");
    setEditEmploymentType(job.employment_type || "");
    setShowEdit(true);
  }

  async function handleUpdateJob() {
    setError(null);
    if (!editTitle.trim()) { setError("Job title is required."); return; }
    if (!params.jobId) return;
    
    try {
      setUpdating(true);
      const req = editRequiredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
      const pref = editPreferredSkills.split(/[\n,]+/g).map((s) => s.trim()).filter(Boolean);
      
      await updateJob(params.jobId, {
        title: editTitle.trim(),
        description: editDescription.trim() || null, 
        status: editStatus,
        location: editLocation.trim() || null,
        salary_min: editSalaryMin ? Number(editSalaryMin) : null,
        salary_max: editSalaryMax ? Number(editSalaryMax) : null,
        salary_currency: editSalaryCurrency,
        experience_min_years: editExpMin ? Number(editExpMin) : null,
        experience_max_years: editExpMax ? Number(editExpMax) : null,
        employment_type: editEmploymentType || null,
        required_skills: req.length ? req : null,
        preferred_skills: pref.length ? pref : null,
      });
      
      setShowEdit(false);
      loadData(); // reload job data
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update job.");
    } finally { 
      setUpdating(false); 
    }
  }

  async function loadData() {
    if (!params.jobId) return;
    setLoading(true);
    setError(null);
    setPipelineError(null);
    try {
      const data = await getJobById(params.jobId);
      setJob(data);
      try {
        const pipelineData = await getPipelines(200, 0, params.jobId);
        setPipelines(pipelineData);
      } catch (pipelineErr) {
        setPipelines([]);
        setPipelineError(pipelineErr instanceof Error ? pipelineErr.message : "Unable to load pipeline summary.");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to load job details");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [params.jobId]);

  useEffect(() => {
    if (job) {
      loadSubmissions();
    }
  }, [job]);

  async function loadSubmissions() {
    if (!params.jobId) return;
    setSubmissionsLoading(true);
    setSubmissionsError(null);
    try {
      const response = await getJobSubmissions(params.jobId, { limit: 200, offset: 0 });
      setSubmissions(response.data);
      setSubmissionsTotal(response.total);
    } catch (err) {
      setSubmissionsError(err instanceof ApiError ? err.message : "Unable to load submissions.");
    } finally {
      setSubmissionsLoading(false);
    }
  }

  const handleCopyJD = () => {
    if (job?.raw_jd_text) {
      navigator.clipboard.writeText(job.raw_jd_text);
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        <div className="border-b border-gray-100 pb-4">
          <div className="h-3 w-16 bg-gray-100 rounded animate-pulse mb-3" />
          <div className="h-8 w-96 bg-gray-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-gray-50 rounded-xl animate-pulse border border-gray-100" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
          <div className="lg:col-span-7 space-y-6">
            <div className="h-10 w-full bg-gray-50 rounded animate-pulse border border-gray-100" />
            <div className="h-[400px] w-full bg-gray-50 rounded animate-pulse border border-gray-100" />
          </div>
          <div className="lg:col-span-3 space-y-6">
            <div className="h-48 w-full bg-gray-50 rounded animate-pulse border border-gray-100" />
            <div className="h-32 w-full bg-gray-50 rounded animate-pulse border border-gray-100" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-20 text-center">
        <div className="max-w-md">
          <p className="text-gray-900 font-semibold mb-2">Something went wrong</p>
          <p className="text-gray-500 text-sm mb-6">{error}</p>
          <Button onClick={loadData} variant="outline" size="sm">Retry Loading</Button>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const statusColors: Record<string, string> = {
    open: "bg-emerald-50 text-emerald-700",
    draft: "bg-gray-100 text-gray-600",
    on_hold: "bg-amber-50 text-amber-700",
    filled: "bg-blue-50 text-blue-700",
    closed: "bg-gray-100 text-gray-500",
    cancelled: "bg-red-50 text-red-700",
  };

  const urgencyColors: Record<string, string> = {
    normal: "bg-gray-50 text-gray-500",
    high: "bg-orange-50 text-orange-700",
    critical: "bg-red-50 text-red-700",
  };

  const pipelineSummary = {
    total: pipelines.length,
    applied: pipelines.filter((item) => item.stage === "applied").length,
    screening: pipelines.filter((item) => item.stage === "screening").length,
    interview: pipelines.filter((item) => item.stage === "interview").length,
    offered: pipelines.filter((item) => item.stage === "offer").length,
    hired: pipelines.filter((item) => item.stage === "placed").length,
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* ── HEADER ────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur-md pb-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => router.back()}
          className="text-sm font-medium text-gray-500 hover:text-gray-900 mb-4 flex items-center gap-2 transition-colors w-fit pt-2"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Jobs
        </button>
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                {job.title}
              </h1>
              <div className="flex items-center gap-2 hidden sm:flex">
                <Badge className={`${statusColors[job.status] || statusColors.draft} border-none`}>
                  {job.status.replace("_", " ")}
                </Badge>
                {job.urgency && (
                  <Badge className={`${urgencyColors[job.urgency] || urgencyColors.normal} border-none`}>
                    {job.urgency}
                  </Badge>
                )}
              </div>
            </div>
            {/* Mobile badges */}
            <div className="flex items-center gap-2 mt-2 sm:hidden">
                <Badge className={`${statusColors[job.status] || statusColors.draft} border-none`}>
                  {job.status.replace("_", " ")}
                </Badge>
                {job.urgency && (
                  <Badge className={`${urgencyColors[job.urgency] || urgencyColors.normal} border-none`}>
                    {job.urgency}
                  </Badge>
                )}
            </div>
          </div>
          <div className="flex items-center gap-3 ml-4">
            <ActionMenu onEdit={openEditPanel} />
          </div>
        </div>
      </div>


      {/* ── MAIN LAYOUT ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-10 gap-8">
        
        {/* Left Column (70%) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="border-b border-gray-200 sticky top-20 bg-white/95 backdrop-blur z-20 pt-2">
            <nav className="flex space-x-8 overflow-x-auto scrollbar-hide">
              {(["overview", "raw_jd"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`
                    whitespace-nowrap py-3 px-1 text-sm font-bold transition-all border-b-2
                    ${activeTab === tab
                      ? "border-indigo-600 text-indigo-600"
                      : "border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300"}
                  `}
                >
                  <span className="capitalize">
                    {tab === "raw_jd" ? "Raw JD" : tab}
                  </span>
                </button>
              ))}
            </nav>
          </div>

          <div className="min-h-[400px]">
            {activeTab === "overview" && (
              <div className="animate-in fade-in duration-300 space-y-6">
                <div className="bg-white rounded-xl border border-gray-200 p-6 sm:p-8 shadow-sm">
                   <h2 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
                     <FileText className="w-5 h-5 text-indigo-500" /> Job Description
                   </h2>
                   {job.description ? (
                     <div className="text-[15px] text-gray-700 leading-relaxed whitespace-pre-wrap font-medium">
                       {job.description}
                     </div>
                   ) : (
                     <p className="italic text-gray-400 text-sm">No description provided.</p>
                   )}
                   
                   <div className="mt-8 pt-6 border-t border-gray-100 flex items-center gap-4">
                     <Button variant="outline" onClick={() => setActiveTab('raw_jd')} className="text-sm font-medium border-gray-300 flex items-center gap-2 rounded-lg shadow-sm hover:bg-gray-50 text-gray-700">
                       <FileText className="w-4 h-4" /> View Full JD
                     </Button>
                   </div>
                </div>

                {/* Job Details Card */}
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                  <h3 className="text-base font-bold text-gray-900 mb-5 flex items-center gap-2">
                    <Briefcase className="w-5 h-5 text-gray-400" /> Job Details
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500 flex items-center gap-2"><MapPin className="w-4 h-4" /> Location</span>
                      <span className="text-sm font-semibold text-gray-900">{job.location || "Not specified"}</span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500 flex items-center gap-2"><Briefcase className="w-4 h-4" /> Employment Type</span>
                      <span className="text-sm font-semibold text-gray-900 capitalize">{job.employment_type?.replace('_', ' ') || "Not specified"}</span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500 flex items-center gap-2"><Banknote className="w-4 h-4" /> Salary</span>
                      <span className="text-sm font-semibold text-gray-900">{formatSalary(job.salary_min, job.salary_currency)} {job.salary_max ? `- ${formatSalary(job.salary_max, job.salary_currency)}` : ''}</span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500 flex items-center gap-2"><Clock className="w-4 h-4" /> Experience</span>
                      <span className="text-sm font-semibold text-gray-900">{job.experience_min_years !== null && job.experience_min_years !== undefined ? `${job.experience_min_years} - ${job.experience_max_years || '+'} years` : "Not specified"}</span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500">Organization Unit</span>
                      <span className="text-sm font-semibold text-gray-900 truncate max-w-[120px]">{job.organization_id ? job.organization_id.split("-")[0] : "Not set"}</span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500">Client Account</span>
                      <span className="text-sm font-semibold text-gray-900 truncate max-w-[120px]">
                        {job.client_id ? job.client_id.split("-")[0] : "Internal"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                      <span className="text-sm text-gray-500">Created By</span>
                      <span className="text-sm font-semibold text-gray-900 truncate max-w-[120px]">{job.created_by || "System"}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Created On</span>
                      <span className="text-sm font-semibold text-gray-900">{formatDate(job.created_at)}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "raw_jd" && (
              <div className="animate-in fade-in duration-300">
                <div className="bg-white rounded-xl border border-gray-200 p-6 sm:p-8 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 border-b border-gray-100 pb-4 gap-4">
                    <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                       <FileText className="w-5 h-5 text-indigo-500" /> Raw Job Description
                    </h2>
                    <Button variant="outline" size="sm" onClick={handleCopyJD} className="text-xs font-medium border-gray-300 text-gray-700 h-8 gap-2 hover:bg-gray-50">
                      <Clipboard className="w-3.5 h-3.5" />
                      Copy Text
                    </Button>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-6 border border-gray-100">
                    {job.raw_jd_text ? (
                      <pre className="text-gray-700 text-sm font-mono whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
                        {job.raw_jd_text}
                      </pre>
                    ) : (
                      <p className="text-sm text-gray-400 italic">No JD available.</p>
                    )}
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>

        {/* Right Column (30%) */}
        <div className="lg:col-span-3 space-y-6">
          
          {/* Skills Panel */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm sticky top-24">
            <h3 className="text-base font-bold text-gray-900 mb-6 flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-500" /> Skills
            </h3>
            
            <div className="space-y-6">
              <div>
                <h4 className="text-xs uppercase font-bold text-gray-500 tracking-wider mb-3">Required Skills</h4>
                {job.required_skills && job.required_skills.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {job.required_skills.map((skill, i) => (
                      <span key={i} className="px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 text-xs font-semibold border border-indigo-100 shadow-sm transition-transform hover:-translate-y-0.5 cursor-default">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm italic">No skills listed</p>
                )}
              </div>
              
              <div>
                <h4 className="text-xs uppercase font-bold text-gray-500 tracking-wider mb-3">Preferred Skills</h4>
                {job.preferred_skills && job.preferred_skills.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {job.preferred_skills.map((skill, i) => (
                      <span key={i} className="px-2.5 py-1 rounded bg-gray-50 text-gray-600 text-xs font-medium border border-gray-200 shadow-sm transition-transform hover:-translate-y-0.5 cursor-default">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm italic">No skills listed</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Edit Job Slide-In Panel ─────────────────────────────────── */}
      {showEdit && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Overlay */}
          <div 
            className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" 
            onClick={() => setShowEdit(false)}
          />
          
          {/* Panel */}
          <div className="relative w-full max-w-[480px] bg-white shadow-2xl h-full flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b shrink-0">
              <h2 className="text-xl font-semibold text-slate-800">Edit Job</h2>
              <button 
                onClick={() => setShowEdit(false)} 
                className="text-slate-400 hover:text-slate-600 text-2xl font-bold p-1"
              >
                ✕
              </button>
            </div>
            
            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 text-sm">
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Title *</label>
                  <Input placeholder="Software Engineer" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
                  <textarea 
                    className="w-full h-32 rounded-md border border-slate-200 p-2 text-sm resize-none focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                    placeholder="Describe the role..."
                    value={editDescription} 
                    onChange={(e) => setEditDescription(e.target.value)} 
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Location</label>
                  <Input placeholder="e.g. Remote, San Francisco" value={editLocation} onChange={(e) => setEditLocation(e.target.value)} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Min Exp (Years)</label>
                    <Input type="number" placeholder="0" value={editExpMin} onChange={(e) => setEditExpMin(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Max Exp (Years)</label>
                    <Input type="number" placeholder="5" value={editExpMax} onChange={(e) => setEditExpMax(e.target.value)} />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2">
                  <label className="block text-xs font-medium text-slate-500">Salary Range</label>
                  <div className="flex gap-2">
                    <Input className="flex-1" type="number" placeholder="Min" value={editSalaryMin} onChange={(e) => setEditSalaryMin(e.target.value)} />
                    <Input className="flex-1" type="number" placeholder="Max" value={editSalaryMax} onChange={(e) => setEditSalaryMax(e.target.value)} />
                    <select 
                      className="rounded-md border border-slate-200 px-2 py-2 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                      value={editSalaryCurrency} 
                      onChange={(e) => setEditSalaryCurrency(e.target.value)}
                    >
                      <option>USD</option><option>INR</option><option>EUR</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
                    <select 
                      className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                      value={editStatus} 
                      onChange={(e) => setEditStatus(e.target.value as JobStatus)}
                    >
                      <option value="draft">Draft</option>
                      <option value="open">Open</option>
                      <option value="on_hold">On Hold</option>
                      <option value="cancelled">Cancelled</option>
                      <option value="closed">Closed (Legacy)</option>
                      <option value="filled">Filled</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Employment Type</label>
                    <select 
                      className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                      value={editEmploymentType} 
                      onChange={(e) => setEditEmploymentType(e.target.value)}
                    >
                      <option value="">(None)</option>
                      <option value="full_time">Full Time</option>
                      <option value="part_time">Part Time</option>
                      <option value="contract">Contract</option>
                      <option value="internship">Internship</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Required Skills (comma/newline)</label>
                  <textarea 
                    className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                    value={editRequiredSkills} 
                    onChange={(e) => setEditRequiredSkills(e.target.value)} 
                    placeholder="Python, FastAPI, AWS" 
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Preferred Skills (comma/newline)</label>
                  <textarea 
                    className="h-24 w-full rounded-md border border-slate-200 p-2 text-sm resize-none focus:ring-2 focus:ring-indigo-400 focus:outline-none" 
                    value={editPreferredSkills} 
                    onChange={(e) => setEditPreferredSkills(e.target.value)} 
                    placeholder="Redis, Docker, Terraform" 
                  />
                </div>
              </div>
            </div>

            {/* Sticky Footer */}
            <div className="p-6 border-t bg-slate-50 shrink-0">
              <Button
                className="w-full py-6 text-lg bg-indigo-600 hover:bg-indigo-700"
                disabled={updating}
                onClick={handleUpdateJob}
              >
                {updating ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
=======
/** Legacy route; job detail lives under `/dashboard/jobs/[id]`. */
export default async function JobDetailRedirect({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  redirect(`/dashboard/jobs/${jobId}`);
>>>>>>> 3b3e2c07 (new roles and recruiter dashboard)
}
