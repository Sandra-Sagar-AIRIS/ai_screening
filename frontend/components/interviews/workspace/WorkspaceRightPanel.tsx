"use client";

import { useState } from "react";
import { ClipboardList, Settings2 } from "lucide-react";
import { NotesPanel } from "./NotesPanel";
import { ControlsPanel } from "./ControlsPanel";
import type { Interview, InterviewFeedback, InterviewNote, InterviewParticipant } from "@/lib/api/types";

type Tab = "notes" | "controls";

export function WorkspaceRightPanel({
  interviewId,
  interview,
  participants,
  feedbackList,
  initialNotes,
  currentUserId,
  onScorecardOpen,
  onInterviewUpdated,
}: {
  interviewId: string;
  interview: Interview;
  participants: InterviewParticipant[];
  feedbackList: InterviewFeedback[];
  initialNotes: InterviewNote[];
  currentUserId: string | null;
  onScorecardOpen: () => void;
  onInterviewUpdated: (updated: Interview) => void;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("notes");

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex shrink-0 border-b border-gray-200 bg-white">
        <button
          onClick={() => setActiveTab("notes")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
            activeTab === "notes"
              ? "border-[#FF5A1F] text-[#FF5A1F]"
              : "border-transparent text-gray-500 hover:text-gray-800"
          }`}
        >
          <ClipboardList className="w-3.5 h-3.5" />
          Notes
        </button>
        <button
          onClick={() => setActiveTab("controls")}
          className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
            activeTab === "controls"
              ? "border-[#FF5A1F] text-[#FF5A1F]"
              : "border-transparent text-gray-500 hover:text-gray-800"
          }`}
        >
          <Settings2 className="w-3.5 h-3.5" />
          Controls
        </button>
      </div>

      {/* Panel content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className={activeTab === "notes" ? "h-full p-4 overflow-y-auto" : "hidden"}>
          <NotesPanel interviewId={interviewId} initialNotes={initialNotes} />
        </div>
        <div className={activeTab === "controls" ? "h-full p-4 overflow-y-auto" : "hidden"}>
          <ControlsPanel
            interview={interview}
            participants={participants}
            feedbackList={feedbackList}
            currentUserId={currentUserId}
            onScorecardOpen={onScorecardOpen}
            onInterviewUpdated={onInterviewUpdated}
          />
        </div>
      </div>
    </div>
  );
}
