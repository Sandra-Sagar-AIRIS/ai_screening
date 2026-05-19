"use client";

/**
 * MeetingContainer
 *
 * Center-panel meeting host for the AIRIS interview workspace.
 *
 * Join modes (no popups, no window.open):
 *
 *  "livekit"  — LiveKit SDK renders the video call directly inline.
 *               Requires LIVEKIT_API_KEY / LIVEKIT_API_SECRET / LIVEKIT_WS_URL
 *               in backend/.env.  Fully embedded, no external windows.
 *
 *  "iframe"   — EmbeddedMeetingFrame wraps providers that support cross-origin
 *               iframe embedding (Zoom /wc/, Daily.co, generic URLs).
 *               Falls back to "external" if the browser blocks the frame.
 *
 *  "external" — Provider cannot be embedded (Google Meet, Teams) OR LiveKit is
 *               not yet configured.  Shows a Companion Panel with:
 *               - a plain <a> link the recruiter can click themselves,
 *               - a quick-observation textarea that saves to Notes.
 *               NO window.open, NO popup launcher.
 *
 * Provider routing:
 *   google_meet  → external (X-Frame-Options: SAMEORIGIN — hard browser block)
 *   teams        → external (X-Frame-Options: DENY)
 *   zoom         → iframe → fallback external
 *   daily        → iframe → fallback external
 *   livekit      → livekit SDK (fully embedded, no external windows)
 *   other        → iframe → fallback external
 */

import { memo, useCallback, useEffect, useState } from "react";
import { Copy, ExternalLink, Maximize2, Minimize2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { detectProvider, getProviderConfig } from "@/lib/meeting/providers";
import type { MeetingProvider } from "@/lib/meeting/providers";
import { EmbeddedMeetingFrame } from "./EmbeddedMeetingFrame";
import { LiveKitRoom } from "@/components/interviews/meeting/LiveKitRoom";
import { upsertNote } from "@/lib/api/interviews";

// ── Types ─────────────────────────────────────────────────────────────────

type MeetingState = "not_started" | "connecting" | "active" | "disconnected" | "completed";
type JoinMode = "livekit" | "iframe" | "external";

// ── Sub-components ────────────────────────────────────────────────────────

function ProviderBadge({ provider }: { provider: MeetingProvider }) {
  const config = getProviderConfig(provider);
  const LOGOS: Record<MeetingProvider, string> = {
    google_meet: "G",
    teams: "T",
    zoom: "Z",
    livekit: "L",
    daily: "D",
    other: "📹",
  };
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
      style={{
        backgroundColor: config.bgColor,
        color: config.color,
        borderColor: `${config.color}44`,
      }}
    >
      <span
        className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-black text-white"
        style={{ backgroundColor: config.color }}
      >
        {LOGOS[provider]}
      </span>
      {config.displayName}
    </span>
  );
}

function ActivePulse() {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700">
      <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse shrink-0" />
      Meeting active
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export const MeetingContainer = memo(function MeetingContainer({
  interviewId,
  meetingUrl,
  interviewStatus,
  onMeetingStarted,
}: {
  /**
   * Workspace interview ID.
   * - Used to request a LiveKit token from the backend.
   * - Used to persist quick-capture observations to the Notes API.
   */
  interviewId?: string;
  meetingUrl: string | null;
  interviewStatus: string;
  onMeetingStarted: () => void;
}) {
  const [state, setState] = useState<MeetingState>("not_started");
  const [joinMode, setJoinMode] = useState<JoinMode>("external");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);
  // Quick-capture for Companion Panel
  const [quickNote, setQuickNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [noteSaved, setNoteSaved] = useState(false);

  // When no external meeting URL is provided, default to the embedded LiveKit provider.
  // This ensures AIRIS automatically hosts the video session instead of showing an
  // empty state.  All non-null URLs still go through the normal detectProvider path.
  const provider: MeetingProvider = meetingUrl ? detectProvider(meetingUrl) : "livekit";
  const config = getProviderConfig(provider);

  // ── Resolve the join mode for this provider ─────────────────────────

  const resolveJoinMode = useCallback((): JoinMode => {
    // LiveKit room URL → always use the LiveKit SDK
    if (provider === "livekit") return "livekit";
    // Providers that categorically cannot be iframe-embedded → external link
    if (!config.canEmbed) return "external";
    // All others → attempt iframe embedding
    return "iframe";
  }, [provider, config.canEmbed]);

  // ── Sync with interview status ──────────────────────────────────────

  useEffect(() => {
    if (
      ["completed", "feedback_pending", "feedback_submitted", "cancelled", "no_show"].includes(
        interviewStatus,
      )
    ) {
      setState("completed");
    }
  }, [interviewStatus]);

  // ── Actions ─────────────────────────────────────────────────────────

  const joinMeeting = useCallback(() => {
    if (!meetingUrl && provider !== "livekit") return;
    setState("connecting");
    const mode = resolveJoinMode();
    setJoinMode(mode);

    if (mode === "livekit") {
      // Token fetch + connection is handled entirely by LiveKitRoom component.
      // State transitions come through its onConnected / onDisconnected callbacks.
    } else if (mode === "iframe") {
      // EmbeddedMeetingFrame will fire onReady once loaded.
      // Show "active" optimistically; onBlocked handles the fallback.
      setTimeout(() => {
        setState("active");
        onMeetingStarted();
      }, 800);
    } else {
      // external — recruiter will click the link themselves
      setState("active");
      onMeetingStarted();
    }
  }, [meetingUrl, provider, resolveJoinMode, onMeetingStarted]);

  // ── Auto-launch embedded LiveKit session when no external URL ──────
  //
  // If there is no external meeting link the provider defaults to "livekit"
  // (see above).  Skip the "not_started" holding screen and go straight into
  // the embedded video session so the recruiter lands in an active meeting.
  useEffect(() => {
    if (
      !meetingUrl &&
      provider === "livekit" &&
      state === "not_started" &&
      interviewId
    ) {
      joinMeeting();
    }
  }, [meetingUrl, provider, state, interviewId, joinMeeting]);

  // Called by EmbeddedMeetingFrame when the browser blocks the iframe.
  // Seamlessly switches to "external" mode — NO popup launched.
  const handleIframeBlocked = useCallback(() => {
    setJoinMode("external");
  }, []);

  // Persist a quick observation into the Notes API.
  const saveQuickNote = useCallback(async () => {
    if (!quickNote.trim() || !interviewId) return;
    setSavingNote(true);
    try {
      await upsertNote(interviewId, {
        section: "observations",
        content: quickNote.trim(),
        finalized: false,
      });
      setQuickNote("");
      setNoteSaved(true);
      setTimeout(() => setNoteSaved(false), 2500);
    } catch {
      // Non-fatal
    } finally {
      setSavingNote(false);
    }
  }, [quickNote, interviewId]);

  const copyLink = useCallback(async () => {
    if (!meetingUrl) return;
    await navigator.clipboard.writeText(meetingUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [meetingUrl]);

  const embedUrl =
    config.canEmbed && meetingUrl ? config.getEmbedUrl(meetingUrl) : null;

  const renderIframe =
    state === "active" && joinMode === "iframe" && !!embedUrl;

  const renderLiveKit =
    (state === "connecting" || state === "active") &&
    joinMode === "livekit" &&
    !!interviewId;

  // ── Full layout ────────────────────────────────────────────────────

  return (
    <div
      className={`flex flex-col bg-gray-50 ${isFullscreen ? "fixed inset-0 z-50" : "h-full"}`}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-200 shrink-0">
        <ProviderBadge provider={provider} />
        {state === "active" && <ActivePulse />}
        <div className="ml-auto flex items-center gap-1">
          {state === "active" && meetingUrl && (
            <button
              onClick={() => void copyLink()}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
              {copied ? "Copied!" : "Copy link"}
            </button>
          )}
          {/* "Open in tab" is a plain <a> — the recruiter's deliberate action */}
          {meetingUrl && (
            <a
              href={meetingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open in tab
            </a>
          )}
          <button
            onClick={() => setIsFullscreen((f) => !f)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
            aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 min-h-0 relative overflow-hidden">

        {/* ─ not_started ─────────────────────────────────────────────── */}
        {state === "not_started" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-5 max-w-xs w-full">
              <div
                className="w-24 h-24 rounded-3xl flex items-center justify-center text-4xl mx-auto shadow-sm"
                style={{ backgroundColor: config.bgColor }}
              >
                {provider === "google_meet"
                  ? "📗"
                  : provider === "teams"
                  ? "🟣"
                  : provider === "zoom"
                  ? "🔵"
                  : provider === "livekit"
                  ? "🟢"
                  : provider === "daily"
                  ? "🔷"
                  : "📹"}
              </div>
              <div className="space-y-1.5">
                <p className="text-base font-semibold text-gray-900">
                  {config.displayName}
                </p>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {provider === "livekit"
                    ? "An embedded AIRIS video session will open directly in this panel."
                    : config.canEmbed
                    ? "Meeting will open directly inside this panel."
                    : `${config.displayName} restricts embedding. The meeting link will appear here — click it to join in a new tab while keeping AI Copilot visible.`}
                </p>
              </div>
              <Button
                className="w-full h-10 text-white font-medium"
                style={{ backgroundColor: config.color }}
                onClick={joinMeeting}
              >
                Join Meeting
              </Button>
            </div>
          </div>
        )}

        {/* ─ connecting (non-LiveKit) ─────────────────────────────────── */}
        {state === "connecting" && !renderLiveKit && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-3">
              <div
                className="w-10 h-10 rounded-full border-[3px] border-t-transparent animate-spin mx-auto"
                style={{
                  borderColor: `${config.color}66`,
                  borderTopColor: config.color,
                }}
              />
              <p className="text-sm text-gray-500">
                Connecting to {config.displayName}…
              </p>
            </div>
          </div>
        )}

        {/* ─ LiveKit embedded room ────────────────────────────────────── */}
        {renderLiveKit && (
          <LiveKitRoom
            interviewId={interviewId!}
            onConnected={() => {
              setState("active");
              onMeetingStarted();
            }}
            onDisconnected={() => setState("disconnected")}
            onNotConfigured={() => {
              // LiveKit not configured on this backend — fall back to external link mode
              setJoinMode("external");
              setState("active");
              onMeetingStarted();
            }}
          />
        )}

        {/* ─ iframe embedded meeting ──────────────────────────────────── */}
        {renderIframe && (
          <EmbeddedMeetingFrame
            src={embedUrl!}
            title={`${config.displayName} meeting`}
            onReady={() => {/* iframe loaded successfully */}}
            onBlocked={handleIframeBlocked}
          />
        )}

        {/* ─ External / Companion Panel ───────────────────────────────── */}
        {state === "active" && joinMode === "external" && (
          <div className="h-full flex flex-col items-center justify-center p-6 gap-5">

            {/* Status + provider */}
            <div className="flex items-center gap-3">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl shadow-sm ring-4 ring-green-100 shrink-0"
                style={{ backgroundColor: config.bgColor }}
              >
                {provider === "google_meet"
                  ? "📗"
                  : provider === "teams"
                  ? "🟣"
                  : provider === "zoom"
                  ? "🔵"
                  : provider === "livekit"
                  ? "🟢"
                  : provider === "daily"
                  ? "🔷"
                  : "📹"}
              </div>
              <div>
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse shrink-0" />
                  <p className="text-sm font-semibold text-gray-900">
                    Interview in progress
                  </p>
                </div>
                <p className="text-[11px] text-gray-500 max-w-[220px] leading-snug">
                  {provider === "google_meet" || provider === "teams"
                    ? `${config.displayName} doesn't allow in-app embedding. Use the tab link below, then return here for AI Copilot.`
                    : !meetingUrl
                    ? "LiveKit is not configured on this server. AI Copilot features are still available below."
                    : "Meeting is running. Use the tab link below or switch to a LiveKit room for full embedding."}
                </p>
              </div>
            </div>

            {/* Clickable meeting link — plain <a>, NOT window.open */}
            {meetingUrl && (
              <a
                href={meetingUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm font-medium px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-800 shadow-sm transition-colors"
              >
                <ExternalLink className="w-4 h-4 text-gray-400" />
                Open {config.displayName}
              </a>
            )}

            {/* Quick-capture — saves straight into Notes */}
            {interviewId && (
              <div className="w-full max-w-sm space-y-2">
                <label className="flex items-center gap-1.5 text-[11px] font-medium text-gray-600">
                  <Pencil className="w-3 h-3" />
                  Quick observation
                </label>
                <textarea
                  value={quickNote}
                  onChange={(e) => setQuickNote(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      void saveQuickNote();
                    }
                  }}
                  placeholder="Jot a note about this candidate… (⌘↵ to save)"
                  rows={3}
                  className="w-full text-xs rounded-lg border border-gray-200 bg-white px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/30 focus:border-[#FF5A1F] placeholder:text-gray-300 transition"
                />
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[10px] transition-opacity ${
                      noteSaved ? "text-green-600 opacity-100" : "opacity-0"
                    }`}
                  >
                    ✓ Saved to Notes
                  </span>
                  <button
                    disabled={!quickNote.trim() || savingNote}
                    onClick={() => void saveQuickNote()}
                    className="flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-[#FF5A1F] text-white hover:bg-[#e04e18] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {savingNote ? (
                      <span className="w-3 h-3 border border-white/60 border-t-white rounded-full animate-spin" />
                    ) : (
                      <Pencil className="w-3 h-3" />
                    )}
                    Add to Notes
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─ disconnected ─────────────────────────────────────────────── */}
        {state === "disconnected" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-4 max-w-xs w-full">
              <div className="w-16 h-16 rounded-2xl bg-amber-50 flex items-center justify-center mx-auto text-3xl">
                🔌
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-gray-800">
                  Disconnected from meeting
                </p>
                <p className="text-xs text-gray-400">
                  {provider === "livekit"
                    ? "The meeting room connection was lost. Rejoin to continue."
                    : "The meeting ended or lost connection."}
                </p>
              </div>
              <div className="flex gap-2 justify-center flex-wrap">
                <Button
                  variant="outline"
                  className="gap-1.5 text-xs h-8"
                  onClick={joinMeeting}
                >
                  Rejoin
                </Button>
                {meetingUrl && (
                  <a
                    href={meetingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-gray-200 hover:bg-gray-50 text-gray-700 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Open in tab
                  </a>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─ completed ─────────────────────────────────────────────────── */}
        {state === "completed" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-3 max-w-xs w-full">
              <div className="w-16 h-16 rounded-2xl bg-green-50 flex items-center justify-center mx-auto text-3xl">
                ✓
              </div>
              <p className="text-sm font-semibold text-gray-800">
                Interview session ended
              </p>
              <p className="text-xs text-gray-400">
                Submit your scorecard from the Controls tab in the right panel.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
