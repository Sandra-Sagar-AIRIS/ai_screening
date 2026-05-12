import { Calendar, CheckCircle2, XCircle, MessageSquare, RefreshCw, Clock } from "lucide-react";
import type { Interview } from "@/lib/api/types";
import { InterviewStatusBadge } from "@/components/interviews/InterviewStatusBadge";
import { cn } from "@/lib/utils";

const STATUS_ICON: Record<string, React.ReactNode> = {
  scheduled:        <Clock className="w-3.5 h-3.5" />,
  confirmed:        <Calendar className="w-3.5 h-3.5" />,
  completed:        <CheckCircle2 className="w-3.5 h-3.5" />,
  cancelled:        <XCircle className="w-3.5 h-3.5" />,
  no_show:          <XCircle className="w-3.5 h-3.5" />,
  rescheduled:      <RefreshCw className="w-3.5 h-3.5" />,
  feedback_pending: <MessageSquare className="w-3.5 h-3.5" />,
};

const STATUS_DOT: Record<string, string> = {
  scheduled:        "bg-blue-500",
  confirmed:        "bg-indigo-500",
  completed:        "bg-green-500",
  cancelled:        "bg-red-400",
  no_show:          "bg-orange-500",
  rescheduled:      "bg-yellow-500",
  feedback_pending: "bg-purple-500",
};

const TYPE_LABELS: Record<string, string> = {
  hr:           "HR Interview",
  technical:    "Technical Interview",
  managerial:   "Managerial Interview",
  final:        "Final Interview",
  ai_screening: "AI Screening",
};

interface Props {
  interviews: Interview[];
}

export function InterviewTimeline({ interviews }: Props) {
  const sorted = [...interviews].sort(
    (a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime(),
  );

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">No interview history.</p>
    );
  }

  return (
    <div className="relative space-y-4 pl-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-0.5 before:bg-gradient-to-b before:from-gray-200 before:via-gray-300 before:to-transparent">
      {sorted.map((interview) => {
        const dot = STATUS_DOT[interview.status] ?? "bg-gray-400";
        const label =
          interview.interview_type
            ? TYPE_LABELS[interview.interview_type] ?? interview.interview_type
            : "Interview";
        const date = new Date(interview.scheduled_at);

        return (
          <div key={interview.id} className="relative">
            <div
              className={cn(
                "absolute -left-6 top-1.5 h-4 w-4 rounded-full border-2 border-white shadow-sm",
                dot,
              )}
            />
            <div className="rounded-xl border border-gray-200 bg-white p-3 hover:border-gray-300 transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-gray-900">{label}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    {date.toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}{" "}
                    {date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                  </p>
                  {interview.interviewer_name && (
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      with {interview.interviewer_name}
                    </p>
                  )}
                </div>
                <InterviewStatusBadge status={interview.status} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
