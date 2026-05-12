"use client";

import { useCallback } from "react";
import { InterviewCard } from "@/components/interviews/InterviewCard";
import { deleteInterview, getFeedback, updateInterview } from "@/lib/api/interviews";
import type { Interview, InterviewFeedback, InterviewStatus } from "@/lib/api/types";

interface Props {
  interviews: Interview[];
  feedbackMap?: Map<string, InterviewFeedback[]>;
  onInterviewsChange?: (interviews: Interview[]) => void;
  onRefresh?: () => void;
  canUpdate?: boolean;
  canDelete?: boolean;
  canFeedback?: boolean;
  emptyMessage?: string;
}

export function InterviewList({
  interviews,
  feedbackMap = new Map(),
  onInterviewsChange,
  onRefresh,
  canUpdate = false,
  canDelete = false,
  canFeedback = false,
  emptyMessage = "No interviews scheduled.",
}: Props) {
  const handleStatusChange = useCallback(
    async (id: string, newStatus: InterviewStatus) => {
      try {
        const updated = await updateInterview(id, { status: newStatus });
        onInterviewsChange?.(
          interviews.map((i) => (i.id === id ? updated : i)),
        );
      } catch (err) {
        console.error("Failed to update interview status", err);
      }
    },
    [interviews, onInterviewsChange],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteInterview(id);
        onInterviewsChange?.(interviews.filter((i) => i.id !== id));
      } catch (err) {
        console.error("Failed to delete interview", err);
      }
    },
    [interviews, onInterviewsChange],
  );

  const handleFeedbackSubmit = useCallback(() => {
    onRefresh?.();
  }, [onRefresh]);

  if (interviews.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-gray-500">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {interviews.map((interview) => (
        <InterviewCard
          key={interview.id}
          interview={interview}
          feedback={feedbackMap.get(interview.id) ?? []}
          onStatusChange={handleStatusChange}
          onDelete={handleDelete}
          onFeedbackSubmit={handleFeedbackSubmit}
          canUpdate={canUpdate}
          canDelete={canDelete}
          canFeedback={canFeedback}
        />
      ))}
    </div>
  );
}
