"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Loader2,
  Mic,
  MicOff,
  RefreshCw,
  Send,
  Sparkles,
  WifiOff,
  X,
  FileText,
} from "lucide-react";
import {
  addTranscriptSegment,
  getSuggestions,
  getTranscript,
  markSuggestion,
  openCopilotWs,
  requestSuggestions,
  requestSummary,
  sendWsPing,
  startCopilotSession,
} from "@/lib/api/copilot";
import { useAuthStore } from "@/store/auth-store";
import type {
  AISuggestion,
  CopilotSession,
  CopilotWsEvent,
  TranscriptSegment,
} from "@/lib/api/types";

// ── Constants ─────────────────────────────────────────────────────────────────

const SUGGESTION_TYPE_LABELS: Record<string, string> = {
  follow_up: "Follow-up",
  clarification: "Clarify",
  skill_gap: "Skill gap",
  deep_dive: "Deep dive",
  closing: "Closing",
};

const SUGGESTION_TYPE_COLORS: Record<string, string> = {
  follow_up: "bg-blue-50 text-blue-700 border-blue-200",
  clarification: "bg-yellow-50 text-yellow-700 border-yellow-200",
  skill_gap: "bg-red-50 text-red-700 border-red-200",
  deep_dive: "bg-purple-50 text-purple-700 border-purple-200",
  closing: "bg-green-50 text-green-700 border-green-200",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "text-green-600",
  medium: "text-yellow-600",
  hard: "text-red-600",
};

const SPEAKER_LABELS: Record<string, string> = {
  interviewer: "Interviewer",
  candidate: "Candidate",
  unknown: "Unknown",
};

const SPEAKER_COLORS: Record<string, string> = {
  interviewer: "text-blue-700",
  candidate: "text-green-700",
  unknown: "text-gray-500",
};

// ── SuggestionCard ────────────────────────────────────────────────────────────

function SuggestionCard({
  suggestion,
  onUse,
  onDismiss,
}: {
  suggestion: AISuggestion;
  onUse: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const typeLabel = SUGGESTION_TYPE_LABELS[suggestion.suggestion_type] ?? suggestion.suggestion_type;
  const typeColor = SUGGESTION_TYPE_COLORS[suggestion.suggestion_type] ?? "bg-gray-50 text-gray-600 border-gray-200";
  const diffColor = suggestion.difficulty ? (DIFFICULTY_COLORS[suggestion.difficulty] ?? "") : "";

  return (
    <div
      className={`rounded-lg border p-3 text-sm transition-all ${
        suggestion.used
          ? "border-green-200 bg-green-50 opacity-60"
          : "border-gray-200 bg-white hover:border-[#FF5A1F]/40"
      }`}
    >
      {/* Header row */}
      <div className="flex items-start gap-2">
        <span className={`shrink-0 mt-0.5 inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium ${typeColor}`}>
          {typeLabel}
        </span>
        {suggestion.difficulty && (
          <span className={`shrink-0 mt-0.5 text-[10px] font-medium ${diffColor}`}>
            {suggestion.difficulty}
          </span>
        )}
        {suggestion.used && (
          <span className="shrink-0 mt-0.5 inline-flex items-center gap-1 text-[10px] text-green-600 font-medium ml-auto">
            <CheckCircle2 className="w-3 h-3" /> Used
          </span>
        )}
      </div>

      {/* Question text */}
      <p className="mt-2 font-medium text-gray-800 leading-snug">
        {suggestion.question_text}
      </p>

      {/* Expandable rationale */}
      {suggestion.rationale && (
        <button
          onClick={() => setExpanded((p) => !p)}
          className="mt-1.5 flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? "Hide rationale" : "Why this question?"}
        </button>
      )}
      {expanded && suggestion.rationale && (
        <p className="mt-1.5 text-[11px] text-gray-500 italic leading-relaxed">
          {suggestion.rationale}
        </p>
      )}

      {/* Skills */}
      {suggestion.target_skills && suggestion.target_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {suggestion.target_skills.slice(0, 4).map((s) => (
            <span key={s} className="inline-block rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      {!suggestion.used && !suggestion.dismissed && (
        <div className="mt-2.5 flex gap-2">
          <button
            onClick={() => onUse(suggestion.id)}
            className="flex-1 rounded-md bg-[#FF5A1F] px-2 py-1.5 text-[11px] font-semibold text-white hover:bg-[#e04a14] transition-colors"
          >
            Use this question
          </button>
          <button
            onClick={() => onDismiss(suggestion.id)}
            className="rounded-md border border-gray-200 px-2 py-1.5 text-[11px] text-gray-500 hover:bg-gray-50 transition-colors"
            title="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// ── Summary section ───────────────────────────────────────────────────────────

function SummaryView({ summary }: { summary: Record<string, unknown> | null }) {
  if (!summary) return null;

  const impression = summary.overall_impression as string | undefined;
  const strengths = summary.strengths as string[] | undefined;
  const concerns = summary.concerns as string[] | undefined;
  const recommendation = summary.recommendation as string | undefined;
  const rationale = summary.recommendation_rationale as string | undefined;
  const nextSteps = summary.suggested_next_steps as string[] | undefined;

  const recColors: Record<string, string> = {
    strong_yes: "text-green-700 bg-green-50 border-green-200",
    yes: "text-green-600 bg-green-50 border-green-200",
    maybe: "text-yellow-700 bg-yellow-50 border-yellow-200",
    no: "text-red-600 bg-red-50 border-red-200",
  };

  return (
    <div className="space-y-3">
      {impression && (
        <p className="text-xs text-gray-700 leading-relaxed">{impression}</p>
      )}
      {recommendation && (
        <div className={`inline-flex items-center rounded border px-2 py-1 text-xs font-semibold ${recColors[recommendation] ?? "text-gray-600 bg-gray-50 border-gray-200"}`}>
          Recommendation: {recommendation.replace("_", " ")}
        </div>
      )}
      {rationale && (
        <p className="text-xs text-gray-500 italic">{rationale}</p>
      )}
      {strengths && strengths.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Strengths</p>
          <ul className="space-y-1">
            {strengths.map((s, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-gray-700">
                <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-green-400 mt-1" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
      {concerns && concerns.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Concerns</p>
          <ul className="space-y-1">
            {concerns.map((c, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-gray-700">
                <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-red-400 mt-1" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
      {nextSteps && nextSteps.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Next Steps</p>
          <ul className="space-y-1">
            {nextSteps.map((s, i) => (
              <li key={i} className="text-xs text-gray-700 before:content-['→'] before:mr-1.5 before:text-gray-400">
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Main CopilotPanel ─────────────────────────────────────────────────────────

type ActiveSection = "suggestions" | "transcript" | "summary";

export function CopilotPanel({ interviewId }: { interviewId: string }) {
  const token = useAuthStore((s) => s.token);

  const [session, setSession] = useState<CopilotSession | null>(null);
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [activeSection, setActiveSection] = useState<ActiveSection>("suggestions");
  const [wsConnected, setWsConnected] = useState(false);

  // Loading states
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionReady, setSessionReady] = useState(false); // gates WS — stays true once set
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [notAvailable, setNotAvailable] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Transcript entry
  const [transcriptInput, setTranscriptInput] = useState("");
  const [transcriptSpeaker, setTranscriptSpeaker] = useState<"interviewer" | "candidate">("interviewer");
  const [addingSegment, setAddingSegment] = useState(false);

  // Auto-transcription (Web Speech API)
  const [autoTranscribeOn, setAutoTranscribeOn] = useState(false);
  const [autoTranscribeError, setAutoTranscribeError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // Ref to track auto-transcribe state inside event handler closures
  const autoTranscribeOnRef = useRef(false);
  // Refs to cancel in-flight suggestion/summary polling loops
  const suggestPollRef = useRef<{ cancelled: boolean } | null>(null);
  const summaryPollRef = useRef<{ cancelled: boolean } | null>(null);
  // Ref to the active SpeechRecognition instance
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // ── Load session + initial data ───────────────────────────────────────────

  const loadInitialData = useCallback(async () => {
    setLoadError(null);
    setSessionReady(false);
    try {
      const sess = await startCopilotSession(interviewId);
      setSession(sess);
      setSessionReady(true);
      const [sugs, segs] = await Promise.all([
        getSuggestions(interviewId).catch(() => []),
        getTranscript(interviewId).catch(() => []),
      ]);
      setSuggestions(sugs);
      setTranscript(segs);
    } catch (e: unknown) {
      const status = (e as { status?: number }).status;
      if (status === 503 || status === 404) {
        setNotAvailable(true);
      } else if (status === 403) {
        setNotAvailable(true); // no permission — treat same as disabled
      } else {
        // Unexpected error (500 etc.) — show retry
        const msg = (e instanceof Error ? e.message : null) ?? "Failed to load AI Copilot";
        setLoadError(msg);
      }
    } finally {
      setSessionLoading(false);
    }
  }, [interviewId]);

  useEffect(() => {
    void loadInitialData();
  }, [loadInitialData]);

  // ── WebSocket ─────────────────────────────────────────────────────────────

  const handleWsEvent = useCallback((evt: CopilotWsEvent) => {
    if (evt.type === "suggestion_ready") {
      // Refresh suggestions list
      getSuggestions(interviewId).then(setSuggestions).catch(() => {});
    } else if (evt.type === "summary_ready" || evt.type === "session_updated") {
      startCopilotSession(interviewId).then(setSession).catch(() => {});
    } else if (evt.type === "transcript_added") {
      getTranscript(interviewId).then(setTranscript).catch(() => {});
    }
  }, [interviewId]);

  useEffect(() => {
    // Use `sessionReady` (not `session`) so that session state updates from WS events
    // don't tear down and recreate the WebSocket connection on every event.
    if (!token || !sessionReady || notAvailable) return;

    const ws = openCopilotWs(interviewId, token, {
      onOpen: () => {
        setWsConnected(true);
        pingIntervalRef.current = setInterval(() => sendWsPing(ws), 25000);
      },
      onEvent: handleWsEvent,
      onClose: () => {
        setWsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      },
      onError: () => setWsConnected(false),
    });
    wsRef.current = ws;

    return () => {
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      ws.close();
    };
  }, [token, sessionReady, interviewId, notAvailable, handleWsEvent]);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Keep ref in sync so SpeechRecognition's onend can check without stale closure
  useEffect(() => {
    autoTranscribeOnRef.current = autoTranscribeOn;
  }, [autoTranscribeOn]);

  // Cancel in-flight polls and stop recognition on unmount
  useEffect(() => {
    return () => {
      if (suggestPollRef.current) suggestPollRef.current.cancelled = true;
      if (summaryPollRef.current) summaryPollRef.current.cancelled = true;
      recognitionRef.current?.stop();
    };
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleRequestSuggestions = async () => {
    setSuggestLoading(true);
    const prevCount = suggestions.length;
    try {
      await requestSuggestions(interviewId, { count: 3 });
    } catch {
      setSuggestLoading(false);
      return;
    }

    // Cancel any existing poll loop then start a new one.
    // Poll every 2s up to 10 times (20s total). Stop as soon as new
    // suggestions appear — the WS event will usually beat the timer.
    if (suggestPollRef.current) suggestPollRef.current.cancelled = true;
    const poll = { cancelled: false };
    suggestPollRef.current = poll;

    for (let i = 0; i < 10 && !poll.cancelled; i++) {
      await new Promise<void>((r) => setTimeout(r, 2000));
      if (poll.cancelled) return;
      const updated = await getSuggestions(interviewId).catch(() => null);
      if (poll.cancelled) return;
      if (updated !== null && updated.length > prevCount) {
        setSuggestions(updated);
        setSuggestLoading(false);
        suggestPollRef.current = null;
        return;
      }
    }

    // Timed out — do a final fetch so the list is at least up to date
    if (!poll.cancelled) {
      const final = await getSuggestions(interviewId).catch(() => [] as typeof suggestions);
      setSuggestions(final);
      setSuggestLoading(false);
      suggestPollRef.current = null;
    }
  };

  const handleUseSuggestion = async (id: string) => {
    try {
      const updated = await markSuggestion(interviewId, id, { used: true });
      setSuggestions((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch {
      // silent
    }
  };

  const handleDismissSuggestion = async (id: string) => {
    try {
      await markSuggestion(interviewId, id, { dismissed: true });
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // silent
    }
  };

  // ── Auto-transcription (Web Speech API) ────────────────────────────────────

  function toggleAutoTranscribe() {
    if (autoTranscribeOn) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setAutoTranscribeOn(false);
      setAutoTranscribeError(null);
      return;
    }

    // Cross-browser constructor (Chrome/Edge ship it as webkitSpeechRecognition)
    type SpeechRecognitionCtor = new () => SpeechRecognition;
    const Ctor: SpeechRecognitionCtor | undefined =
      (typeof window !== "undefined" &&
        ((window as unknown as { SpeechRecognition?: SpeechRecognitionCtor }).SpeechRecognition ??
          (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition)) ||
      undefined;

    if (!Ctor) {
      setAutoTranscribeError("Speech recognition is not supported in this browser. Use Chrome or Edge.");
      return;
    }

    setAutoTranscribeError(null);
    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          const text = event.results[i][0].transcript.trim();
          if (!text) continue;
          // Fire-and-forget: save to backend and append to local state
          void (async () => {
            try {
              const seg = await addTranscriptSegment(interviewId, {
                speaker: "interviewer",
                content: text,
                source: "speech",
              });
              setTranscript((prev) => [...prev, seg]);
            } catch {
              // silent — transcript still shown locally via interim state
            }
          })();
        }
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech") return; // not a real error — browser stopped on silence
      setAutoTranscribeOn(false);
      autoTranscribeOnRef.current = false;
      recognitionRef.current = null;
      setAutoTranscribeError(
        event.error === "not-allowed"
          ? "Microphone access denied. Allow mic permission and try again."
          : `Speech recognition error: ${event.error}`,
      );
    };

    recognition.onend = () => {
      // Browser stops recognition after silence; restart automatically if still active
      if (autoTranscribeOnRef.current && recognitionRef.current) {
        try { recognition.start(); } catch { /* already running or page hidden */ }
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
    setAutoTranscribeOn(true);
  }

  const handleAddTranscript = async () => {
    if (!transcriptInput.trim()) return;
    setAddingSegment(true);
    try {
      const seg = await addTranscriptSegment(interviewId, {
        speaker: transcriptSpeaker,
        content: transcriptInput.trim(),
        source: "manual",
      });
      setTranscript((prev) => [...prev, seg]);
      setTranscriptInput("");
    } catch {
      // silent
    } finally {
      setAddingSegment(false);
    }
  };

  const handleRequestSummary = async () => {
    setSummaryLoading(true);
    try {
      await requestSummary(interviewId);
    } catch {
      setSummaryLoading(false);
      return;
    }

    // Cancel any existing poll loop then start a new one.
    // Poll every 3s up to 12 times (36s total). Stop as soon as the summary
    // appears — the WS event will usually beat the timer.
    if (summaryPollRef.current) summaryPollRef.current.cancelled = true;
    const poll = { cancelled: false };
    summaryPollRef.current = poll;

    for (let i = 0; i < 12 && !poll.cancelled; i++) {
      await new Promise<void>((r) => setTimeout(r, 3000));
      if (poll.cancelled) return;
      const sess = await startCopilotSession(interviewId).catch(() => null);
      if (poll.cancelled) return;
      if (sess?.summary) {
        setSession(sess);
        setSummaryLoading(false);
        summaryPollRef.current = null;
        return;
      }
    }

    // Timed out — do a final fetch anyway
    if (!poll.cancelled) {
      const sess = await startCopilotSession(interviewId).catch(() => null);
      if (sess) setSession(sess);
      setSummaryLoading(false);
      summaryPollRef.current = null;
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="w-5 h-5 text-[#FF5A1F] animate-spin" />
      </div>
    );
  }

  if (notAvailable) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2 text-center px-4">
        <Bot className="w-6 h-6 text-gray-300" />
        <p className="text-xs text-gray-400">
          AI Copilot is not enabled on this deployment.
        </p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-40 gap-3 text-center px-4">
        <Bot className="w-6 h-6 text-red-300" />
        <p className="text-xs text-gray-500 max-w-[200px]">{loadError}</p>
        <button
          onClick={() => {
            setSessionLoading(true);
            void loadInitialData();
          }}
          className="flex items-center gap-1 text-xs text-[#FF5A1F] hover:underline"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      </div>
    );
  }

  const activeSuggestions = suggestions.filter((s) => !s.dismissed);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#FF5A1F]" />
          <span className="text-xs font-semibold text-gray-700">AI Copilot</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${wsConnected ? "bg-green-400" : "bg-gray-300"}`}
            title={wsConnected ? "Real-time connected" : "Not connected"}
          />
          {!wsConnected && (
            <span title="WebSocket offline — results appear on next poll">
              <WifiOff className="w-3 h-3 text-gray-400" />
            </span>
          )}
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex shrink-0 border-b border-gray-100 bg-gray-50">
        {(["suggestions", "transcript", "summary"] as ActiveSection[]).map((sec) => {
          const labels: Record<ActiveSection, string> = {
            suggestions: "Suggest",
            transcript: "Transcript",
            summary: "Summary",
          };
          return (
            <button
              key={sec}
              onClick={() => setActiveSection(sec)}
              className={`flex-1 py-1.5 text-[11px] font-medium transition-colors ${
                activeSection === sec
                  ? "text-[#FF5A1F] border-b-2 border-[#FF5A1F] -mb-px bg-white"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              {labels[sec]}
              {sec === "suggestions" && activeSuggestions.length > 0 && (
                <span className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#FF5A1F] text-white text-[9px] font-bold">
                  {activeSuggestions.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {/* ── Suggestions tab ── */}
        {activeSection === "suggestions" && (
          <div className="p-3 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-gray-400">
                Context-aware follow-up questions
              </p>
              <button
                onClick={handleRequestSuggestions}
                disabled={suggestLoading}
                className="flex items-center gap-1 rounded-md bg-[#FF5A1F]/10 px-2 py-1 text-[11px] font-semibold text-[#FF5A1F] hover:bg-[#FF5A1F]/20 disabled:opacity-50 transition-colors"
              >
                {suggestLoading ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                {suggestLoading ? "Generating..." : "Get suggestions"}
              </button>
            </div>

            {activeSuggestions.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <Sparkles className="w-6 h-6 text-gray-200" />
                <p className="text-xs text-gray-400">
                  {suggestLoading
                    ? "AI is generating questions..."
                    : "Click “Get suggestions” to generate follow-up questions."}
                </p>
                {transcript.length > 0 && !suggestLoading && (
                  <p className="text-[11px] text-gray-400">
                    {transcript.length} transcript segment{transcript.length > 1 ? "s" : ""} available for context.
                  </p>
                )}
              </div>
            ) : (
              activeSuggestions.map((s) => (
                <SuggestionCard
                  key={s.id}
                  suggestion={s}
                  onUse={handleUseSuggestion}
                  onDismiss={handleDismissSuggestion}
                />
              ))
            )}
          </div>
        )}

        {/* ── Transcript tab ── */}
        {activeSection === "transcript" && (
          <div className="flex flex-col h-full">
            {/* Segments list */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {transcript.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-6 text-center">
                  <Mic className="w-6 h-6 text-gray-200" />
                  <p className="text-xs text-gray-400">
                    No transcript yet. Add segments below.
                  </p>
                </div>
              ) : (
                transcript.map((seg) => (
                  <div key={seg.id} className="text-xs">
                    <span className={`font-semibold ${SPEAKER_COLORS[seg.speaker] ?? "text-gray-600"}`}>
                      {SPEAKER_LABELS[seg.speaker] ?? seg.speaker}:
                    </span>{" "}
                    <span className="text-gray-700">{seg.content}</span>
                  </div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>

            {/* Add segment form */}
            <div className="shrink-0 border-t border-gray-100 p-2 space-y-2 bg-gray-50">
              {/* Auto-transcribe toggle */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">Auto-transcribe your mic</span>
                <button
                  onClick={toggleAutoTranscribe}
                  className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] font-semibold transition-colors ${
                    autoTranscribeOn
                      ? "bg-red-500 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                  title={autoTranscribeOn ? "Stop auto-transcription" : "Start auto-transcription (mic → transcript)"}
                >
                  {autoTranscribeOn ? (
                    <>
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                      <MicOff className="w-3 h-3" />
                      Stop
                    </>
                  ) : (
                    <>
                      <Mic className="w-3 h-3" />
                      Live
                    </>
                  )}
                </button>
              </div>
              {autoTranscribeError && (
                <p className="text-[10px] text-red-500 leading-tight">{autoTranscribeError}</p>
              )}

              <div className="flex gap-1">
                {(["interviewer", "candidate"] as const).map((sp) => (
                  <button
                    key={sp}
                    onClick={() => setTranscriptSpeaker(sp)}
                    className={`flex-1 py-1 rounded text-[10px] font-medium transition-colors ${
                      transcriptSpeaker === sp
                        ? sp === "interviewer"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-green-100 text-green-700"
                        : "bg-white text-gray-400 border border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    {sp.charAt(0).toUpperCase() + sp.slice(1)}
                  </button>
                ))}
              </div>
              <div className="flex gap-1.5">
                <textarea
                  value={transcriptInput}
                  onChange={(e) => setTranscriptInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleAddTranscript();
                    }
                  }}
                  placeholder="Type what was said... (Enter to add)"
                  rows={2}
                  className="flex-1 rounded-md border border-gray-200 px-2 py-1.5 text-xs resize-none outline-none focus:border-[#FF5A1F]/50 focus:ring-1 focus:ring-[#FF5A1F]/20 transition-colors"
                />
                <button
                  onClick={handleAddTranscript}
                  disabled={addingSegment || !transcriptInput.trim()}
                  className="self-end rounded-md bg-[#FF5A1F] p-2 text-white hover:bg-[#e04a14] disabled:opacity-40 transition-colors"
                >
                  {addingSegment ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Summary tab ── */}
        {activeSection === "summary" && (
          <div className="p-3 space-y-3">
            {session?.summary ? (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-[11px] text-gray-400">Post-interview AI debrief</p>
                  <button
                    onClick={handleRequestSummary}
                    disabled={summaryLoading}
                    className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600"
                  >
                    <RefreshCw className={`w-3 h-3 ${summaryLoading ? "animate-spin" : ""}`} />
                    Regenerate
                  </button>
                </div>
                <SummaryView summary={session.summary as Record<string, unknown>} />
              </>
            ) : (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <FileText className="w-6 h-6 text-gray-200" />
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-600">
                    Generate interview summary
                  </p>
                  <p className="text-[11px] text-gray-400">
                    AI will analyse the transcript and produce a structured debrief.
                  </p>
                </div>
                <button
                  onClick={handleRequestSummary}
                  disabled={summaryLoading || transcript.length === 0}
                  className="flex items-center gap-2 rounded-md bg-[#FF5A1F] px-3 py-2 text-xs font-semibold text-white hover:bg-[#e04a14] disabled:opacity-40 transition-colors"
                >
                  {summaryLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  {summaryLoading ? "Generating summary..." : "Generate summary"}
                </button>
                {transcript.length === 0 && (
                  <p className="text-[11px] text-gray-400">
                    Add transcript segments first.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
