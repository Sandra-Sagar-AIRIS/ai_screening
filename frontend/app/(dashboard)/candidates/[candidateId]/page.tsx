"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, API_BASE_URL } from "@/lib/api/client";
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
import { getJobs } from "@/lib/api/jobs";
import { getPipelines, updatePipeline } from "@/lib/api/pipeline";
import type { Candidate, Job, OrganizationUser, Pipeline } from "@/lib/api/types";
import { getUsers } from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function CandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [interactions, setInteractions] = useState<CandidateInteraction[]>([]);
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

  useEffect(() => {
    if (!params.candidateId) {
      return;
    }
    async function loadData() {
      try {
        const [data, timeline, linkedPipelines, interviewList] = await Promise.all([
          getCandidateById(params.candidateId),
          getCandidateInteractions(params.candidateId, 100, 0),
          getPipelines(200, 0, undefined, params.candidateId),
          getCandidateInterviews(params.candidateId),
        ]);
        setCandidate(data);
        setInteractions(timeline);
        setPipelines(linkedPipelines);
        setInterviews(interviewList);
        setFirstName(data.first_name);
        setLastName(data.last_name);
        setEmail(data.email);
        setPhone(data.phone ?? "");
        setLocation(data.location ?? "");
        setRole(data.role ?? "");
        setYearsExperience(data.years_experience !== null && data.years_experience !== undefined ? String(data.years_experience) : "");
        setSelectedRecruiterId(data.recruiter_id ?? "");
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load candidate details");
        }
      }
    }
    loadData();
  }, [params.candidateId]);

  useEffect(() => {
    async function loadUsers() {
      try {
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
      const response = await fetch(resumeUrl, {
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
        window.open(url, "_blank");
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
      await updateCandidate(candidate.id, { job_id: submitJobId });
      try {
        const linkedPipelines = await getPipelines(200, 0, undefined, candidate.id);
        setPipelines(linkedPipelines);
      } catch {
        setPipelines([]);
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


  return (
    <section className="space-y-4">
      <div className="sticky top-0 z-10 rounded-md border border-slate-200 bg-white/95 p-4 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">
              {candidate.first_name} {candidate.last_name}
            </h1>
            <p className="text-sm text-slate-600">{candidate.role ?? "Role not specified"}</p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">{stageLabel}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-600">
          {candidate.email && <span className="flex items-center gap-1"><span className="font-medium text-slate-800">📧</span> {candidate.email}</span>}
          {candidate.phone && <span className="flex items-center gap-1"><span className="font-medium text-slate-800">📞</span> {candidate.phone}</span>}
          {candidate.location && <span className="flex items-center gap-1"><span className="font-medium text-slate-800">📍</span> {candidate.location}</span>}
          {jobTitle !== "-" && <span className="flex items-center gap-1"><span className="font-medium text-slate-800">💼</span> {jobTitle}</span>}
        </div>
      </div>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Profile</h2>
        <div className="flex items-center gap-2">
        <select
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
          value={submitJobId}
          onChange={(event) => setSubmitJobId(event.target.value)}
        >
          <option value="">Select job</option>
          {jobs.map((job) => (
            <option key={job.id} value={job.id}>
              {job.title}
            </option>
          ))}
        </select>
        <Button variant="outline" onClick={handleSubmitToJob} disabled={!submitJobId || submittingToJob}>
          {submittingToJob ? "Submitting..." : "Submit to Job"}
        </Button>
        {isEditing ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save changes"}
            </Button>
          </div>
        ) : (
          <Button onClick={() => setIsEditing(true)}>Edit candidate</Button>
        )}</div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>
            {isEditing ? (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="First name" />
                <Input value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Last name" />
              </div>
            ) : (
              <>{candidate.first_name} {candidate.last_name}</>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="font-medium">Email:</span> {isEditing ? <Input value={email} onChange={(e) => setEmail(e.target.value)} /> : candidate.email}</p>
          <p><span className="font-medium">Phone:</span> {isEditing ? <Input value={phone} onChange={(e) => setPhone(e.target.value)} /> : (candidate.phone ?? "-")}</p>
          <p><span className="font-medium">Location:</span> {isEditing ? <Input value={location} onChange={(e) => setLocation(e.target.value)} /> : (candidate.location ?? "-")}</p>
          <p><span className="font-medium">Role:</span> {isEditing ? <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role / Title" /> : (candidate.role ?? "-")}</p>
          <p><span className="font-medium">Years Experience:</span> {isEditing ? <Input type="number" min={0} value={yearsExperience} onChange={(e) => setYearsExperience(e.target.value)} /> : (candidate.years_experience !== null && candidate.years_experience !== undefined ? `${candidate.years_experience} years` : "-")}</p>
          {candidate.experience_summary && <p><span className="font-medium">Experience:</span> {candidate.experience_summary}</p>}
          {candidate.education && <p><span className="font-medium">Education:</span> {candidate.education}</p>}
        </CardContent>
      </Card>


      <Card>
        <CardHeader>
          <CardTitle>Resume</CardTitle>
        </CardHeader>
        <CardContent>
          {candidate.resume_file_name || candidate.resume_s3_key ? (
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 text-red-600 text-lg">📄</div>
                <div>
                  <p className="text-sm font-medium text-slate-800">{candidate.resume_file_name ?? "Resume"}</p>
                  <p className="text-xs text-slate-500">Resume document</p>
                </div>
              </div>
              <div className="flex gap-2">
                {candidate.resume_s3_key ? (
                  <>
                    <Button size="sm" variant="outline" onClick={() => handleResumeAction("open")}>Open</Button>
                    <Button size="sm" onClick={() => handleResumeAction("download")}>⬇ Download</Button>
                  </>
                ) : (
                  <span className="text-xs text-slate-400">File unavailable</span>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No resume uploaded for this candidate.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Applied Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {sortedPipelines.length === 0 ? (
            <p className="text-sm text-slate-500">No jobs applied yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-2 py-2">Job</th>
                    <th className="px-2 py-2">Stage</th>
                    <th className="px-2 py-2">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPipelines.map((pipeline) => (
                    <tr key={pipeline.id} className="border-b border-slate-100">
                      <td className="px-2 py-2">{jobs.find((job) => job.id === pipeline.job_id)?.title ?? pipeline.job_id}</td>
                      <td className="px-2 py-2">
                        <select
                          className="rounded-md border border-slate-200 px-2 py-1 text-xs"
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
                      <td className="px-2 py-2 text-xs text-slate-500">{new Date(pipeline.updated_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      <h2 className="text-lg font-semibold">Interviews</h2>
      <Card>
        <CardHeader>
          <CardTitle>Schedule Interview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
            <Input placeholder="Interviewer name" value={interviewerName} onChange={(e) => setInterviewerName(e.target.value)} />
            <select
              className="rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={interviewType}
              onChange={(e) => setInterviewType(e.target.value as "HR" | "TECH")}
            >
              <option value="HR">HR</option>
              <option value="TECH">TECH</option>
            </select>
            <Button onClick={handleScheduleInterview}>Schedule</Button>
          </div>
          {interviews.length === 0 ? (
            <p className="text-slate-500">No interviews scheduled.</p>
          ) : (
            interviews.map((interview) => (
              <div key={interview.id} className="rounded-md border border-slate-200 p-3">
                <p className="font-medium">{interview.interviewer_name ?? "Interviewer TBD"}</p>
                <p className="text-xs text-slate-500">
                  {new Date(interview.scheduled_at).toLocaleString()} | {interview.status}
                </p>
                <p className="text-xs text-slate-600">
                  Type: {interviewMetaById.get(interview.id)?.interview_type ?? "HR"} | Rating:{" "}
                  {interviewMetaById.get(interview.id)?.rating ?? "-"}
                </p>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-4">
                  <Input
                    type="datetime-local"
                    value={rescheduleTimes[interview.id] ?? ""}
                    onChange={(e) => setRescheduleTimes((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                  />
                  <Button
                    variant="outline"
                    onClick={() => handleReschedule(interview.id)}
                    disabled={interviewUpdatingId === interview.id || !rescheduleTimes[interview.id]}
                  >
                    Reschedule
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleCancelInterview(interview.id)}
                    disabled={interviewUpdatingId === interview.id || interview.status === "cancelled"}
                  >
                    Cancel
                  </Button>
                </div>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-4">
                  <Input
                    placeholder="Feedback notes"
                    value={feedbackNotes[interview.id] ?? ""}
                    onChange={(e) => setFeedbackNotes((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                  />
                  <select
                    className="rounded-md border border-slate-200 px-3 py-2 text-sm"
                    value={feedbackRatings[interview.id] ?? ""}
                    onChange={(e) => setFeedbackRatings((prev) => ({ ...prev, [interview.id]: e.target.value }))}
                  >
                    <option value="">Rating</option>
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                    <option value="5">5</option>
                  </select>
                  <Button
                    variant="outline"
                    onClick={() => handleSaveFeedback(interview.id)}
                    disabled={interviewUpdatingId === interview.id}
                  >
                    Save feedback
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
      <h2 className="text-lg font-semibold">Timeline</h2>
      <Card>
        <CardHeader>
          <CardTitle>Timeline / Interactions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex gap-2">
            <Input placeholder="Add note" value={newNote} onChange={(e) => setNewNote(e.target.value)} />
            <Button variant="outline" onClick={handleAddNote} disabled={addingNote || !newNote.trim()}>
              {addingNote ? "Adding..." : "Add Note"}
            </Button>
          </div>
          {orderedTimeline.length === 0 ? (
            <p className="text-slate-500">No interactions yet.</p>
          ) : (
            orderedTimeline.map((item) => (
              <div key={item.id} className="rounded-md border border-slate-200 p-3">
                <p className="font-medium">{item.title ?? item.interaction_type}</p>
                <p className="text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
                {item.body ? <p className="mt-1">{item.body}</p> : null}
                {item.metadata ? (
                  <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs">
                    {JSON.stringify(item.metadata, null, 2)}
                  </pre>
                ) : null}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </section>
  );
}
