"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, Calendar, Clock, Link2, MapPin, User, FileText, Briefcase, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createInterview } from "@/lib/api/interviews";
import type { Interview, InterviewType, MeetingType, Job, Pipeline } from "@/lib/api/types";

const MEETING_TYPES: { value: MeetingType; label: string }[] = [
  { value: "virtual",   label: "Virtual" },
  { value: "in_person", label: "In Person" },
  { value: "phone",     label: "Phone" },
  { value: "hybrid",    label: "Hybrid" },
];

const INTERVIEW_TYPES: { value: InterviewType; label: string }[] = [
  { value: "hr",           label: "HR" },
  { value: "technical",    label: "Technical" },
  { value: "managerial",   label: "Managerial" },
  { value: "final",        label: "Final" },
  { value: "ai_screening", label: "AI Screening" },
];

const DURATIONS = [30, 45, 60, 90, 120];

interface Props {
  pipelines: Pipeline[];
  jobs: Job[];
  open: boolean;
  onClose: () => void;
  onCreated: (interview: Interview) => void;
}

interface FormState {
  pipeline_id: string;
  interview_type: InterviewType | "";
  meeting_type: MeetingType | "";
  date: string;
  time: string;
  duration_minutes: string;
  interviewer_name: string;
  meeting_link: string;
  location: string;
  notes: string;
}

interface FieldError {
  pipeline_id?: string;
  date?: string;
  time?: string;
  general?: string;
}

function buildEmptyForm(pipelines: Pipeline[]): FormState {
  return {
    pipeline_id: pipelines[0]?.id ?? "",
    interview_type: "hr",
    meeting_type: "virtual",
    date: "",
    time: "",
    duration_minutes: "60",
    interviewer_name: "",
    meeting_link: "",
    location: "",
    notes: "",
  };
}

export function ScheduleInterviewModal({ pipelines, jobs, open, onClose, onCreated }: Props) {
  const [form, setForm] = useState<FormState>(() => buildEmptyForm(pipelines));
  const [errors, setErrors] = useState<FieldError>({});
  const [submitting, setSubmitting] = useState(false);
  const firstInputRef = useRef<HTMLSelectElement>(null);

  // Reset form and pre-fill date/time whenever modal opens
  useEffect(() => {
    if (open) {
      const now = new Date();
      now.setHours(now.getHours() + 1, 0, 0, 0);
      setForm({
        ...buildEmptyForm(pipelines),
        date: now.toISOString().split("T")[0],
        time: `${String(now.getHours()).padStart(2, "0")}:00`,
      });
      setErrors({});
      setTimeout(() => firstInputRef.current?.focus(), 50);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const set = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined, general: undefined }));
  }, []);

  function validate(): boolean {
    const errs: FieldError = {};
    if (!form.pipeline_id) errs.pipeline_id = "Please select a job";
    if (!form.date) errs.date = "Date is required";
    if (!form.time) errs.time = "Time is required";
    if (form.date && form.time) {
      const dt = new Date(`${form.date}T${form.time}`);
      if (dt <= new Date()) errs.date = "Must be in the future";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    try {
      const scheduledAt = new Date(`${form.date}T${form.time}`).toISOString();
      const interview = await createInterview({
        pipeline_id: form.pipeline_id,
        interview_type: form.interview_type || undefined,
        meeting_type: form.meeting_type || undefined,
        scheduled_at: scheduledAt,
        duration_minutes: form.duration_minutes ? Number(form.duration_minutes) : undefined,
        interviewer_name: form.interviewer_name.trim() || undefined,
        meeting_link: form.meeting_link.trim() || undefined,
        location: form.location.trim() || undefined,
        notes: form.notes.trim() || undefined,
      });
      onCreated(interview);
      onClose();
    } catch (err) {
      setErrors({ general: err instanceof Error ? err.message : "Failed to schedule interview." });
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  const showJobSelector = pipelines.length > 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-[#FF5A1F]/10 flex items-center justify-center">
              <Calendar className="w-4 h-4 text-[#FF5A1F]" />
            </div>
            <h2 className="text-base font-semibold text-gray-900">Schedule Interview</h2>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-gray-400 hover:text-gray-700"
            onClick={onClose}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Form */}
        <form id="schedule-interview-form" onSubmit={handleSubmit} className="px-6 py-5 space-y-4 overflow-y-auto max-h-[70vh]">
          {/* Job selector — only shown when candidate has multiple eligible pipelines */}
          {showJobSelector && (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
                <Briefcase className="w-3 h-3" /> Job <span className="text-red-500">*</span>
              </label>
              <select
                ref={firstInputRef}
                className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] bg-white ${
                  errors.pipeline_id ? "border-red-400" : "border-gray-200"
                }`}
                value={form.pipeline_id}
                onChange={(e) => set("pipeline_id", e.target.value)}
              >
                <option value="">Select a job…</option>
                {pipelines.map((p) => {
                  const job = jobs.find((j) => j.id === p.job_id);
                  return (
                    <option key={p.id} value={p.id}>
                      {job?.title ?? p.job_id} ({p.stage})
                    </option>
                  );
                })}
              </select>
              {errors.pipeline_id && <p className="text-xs text-red-600">{errors.pipeline_id}</p>}
            </div>
          )}

          {/* Interview Type + Meeting Type row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">Round Type</label>
              <select
                ref={showJobSelector ? undefined : firstInputRef}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] bg-white"
                value={form.interview_type}
                onChange={(e) => set("interview_type", e.target.value as InterviewType)}
              >
                {INTERVIEW_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
                <Video className="w-3 h-3" /> Meeting Type
              </label>
              <select
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] bg-white"
                value={form.meeting_type}
                onChange={(e) => set("meeting_type", e.target.value as MeetingType)}
              >
                {MEETING_TYPES.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Date & Time row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> Date <span className="text-red-500">*</span>
              </label>
              <Input
                type="date"
                className={`text-sm h-9 ${errors.date ? "border-red-400 focus:border-red-400 focus:ring-red-400" : ""}`}
                value={form.date}
                onChange={(e) => set("date", e.target.value)}
              />
              {errors.date && <p className="text-xs text-red-600">{errors.date}</p>}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Time <span className="text-red-500">*</span>
              </label>
              <Input
                type="time"
                className={`text-sm h-9 ${errors.time ? "border-red-400 focus:border-red-400 focus:ring-red-400" : ""}`}
                value={form.time}
                onChange={(e) => set("time", e.target.value)}
              />
              {errors.time && <p className="text-xs text-red-600">{errors.time}</p>}
            </div>
          </div>

          {/* Duration */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Duration
            </label>
            <div className="flex gap-1.5 flex-wrap">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => set("duration_minutes", String(d))}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    form.duration_minutes === String(d)
                      ? "border-[#FF5A1F] bg-[#FF5A1F]/10 text-[#FF5A1F]"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {d} min
                </button>
              ))}
              <Input
                type="number"
                min={1}
                max={480}
                placeholder="Custom"
                className="w-20 h-7 text-xs"
                value={DURATIONS.includes(Number(form.duration_minutes)) ? "" : form.duration_minutes}
                onChange={(e) => set("duration_minutes", e.target.value)}
              />
            </div>
          </div>

          {/* Interviewer */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
              <User className="w-3 h-3" /> Interviewer Name
            </label>
            <Input
              placeholder="e.g. Jane Smith"
              className="text-sm h-9"
              value={form.interviewer_name}
              onChange={(e) => set("interviewer_name", e.target.value)}
            />
          </div>

          {/* Meeting Link */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
              <Link2 className="w-3 h-3" /> Meeting Link
            </label>
            <Input
              type="url"
              placeholder="https://meet.google.com/..."
              className="text-sm h-9"
              value={form.meeting_link}
              onChange={(e) => set("meeting_link", e.target.value)}
            />
          </div>

          {/* Location */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
              <MapPin className="w-3 h-3" /> Location
            </label>
            <Input
              placeholder="Room name or address (optional)"
              className="text-sm h-9"
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
            />
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-700 flex items-center gap-1">
              <FileText className="w-3 h-3" /> Notes
            </label>
            <textarea
              rows={3}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[#FF5A1F] focus:ring-1 focus:ring-[#FF5A1F] resize-none"
              placeholder="Interview instructions, topics to cover..."
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
            />
          </div>

          {errors.general && (
            <p className="text-sm text-red-600 rounded-lg bg-red-50 border border-red-200 px-3 py-2">
              {errors.general}
            </p>
          )}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="schedule-interview-form"
            className="bg-[#FF5A1F] hover:bg-[#E54E1A] text-white min-w-[120px]"
            disabled={submitting}
          >
            {submitting ? "Scheduling…" : "Schedule"}
          </Button>
        </div>
      </div>
    </div>
  );
}
