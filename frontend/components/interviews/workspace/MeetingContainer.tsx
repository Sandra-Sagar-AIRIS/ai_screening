"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { Copy, ExternalLink, Maximize2, Minimize2, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { detectProvider, getProviderConfig, openMeetingPopup } from "@/lib/meeting/providers";
import type { MeetingProvider } from "@/lib/meeting/providers";

// ── Types ────────────────────────────────────────────────────────────────────

type MeetingState = "not_started" | "connecting" | "active" | "disconnected" | "completed";

type JoinMode = "popup" | "iframe";

// ── Sub-components ───────────────────────────────────────────────────────────

function ProviderBadge({ provider }: { provider: MeetingProvider }) {
  const config = getProviderConfig(provider);
  const LOGOS: Record<MeetingProvider, string> = {
    google_meet: "G",
    teams: "T",
    zoom: "Z",
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

// ── Main component ───────────────────────────────────────────────────────────

export const MeetingContainer = memo(function MeetingContainer({
  meetingUrl,
  interviewStatus,
  onMeetingStarted,
}: {
  meetingUrl: string | null;
  interviewStatus: string;
  onMeetingStarted: () => void;
}) {
  const [state, setState] = useState<MeetingState>("not_started");
  const [joinMode, setJoinMode] = useState<JoinMode>("popup");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [iframeBlocked, setIframeBlocked] = useState(false);

  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const provider = meetingUrl ? detectProvider(meetingUrl) : "other";
  const config = getProviderConfig(provider);

  // ── Sync with interview status changes ─────────────────────────────────

  useEffect(() => {
    if (["completed", "feedback_pending", "feedback_submitted", "cancelled", "no_show"].includes(interviewStatus)) {
      setState("completed");
      if (pollRef.current) clearInterval(pollRef.current);
    }
  }, [interviewStatus]);

  // ── Popup monitor ───────────────────────────────────────────────────────

  const startPollPopup = useCallback((popup: Window) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      if (popup.closed) {
        clearInterval(pollRef.current!);
        setState((prev) => (prev === "active" ? "disconnected" : prev));
      }
    }, 2000);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ── Actions ─────────────────────────────────────────────────────────────

  const joinMeeting = useCallback(() => {
    if (!meetingUrl) return;
    setState("connecting");

    const embedUrl = config.canEmbed ? config.getEmbedUrl(meetingUrl) : null;

    if (embedUrl && !iframeBlocked) {
      // Iframe path (Zoom web client / generic)
      setJoinMode("iframe");
      setTimeout(() => {
        setState("active");
        onMeetingStarted();
      }, 1200);
    } else {
      // Popup path (Google Meet, Teams, iframe-blocked)
      setJoinMode("popup");
      const popup = openMeetingPopup(meetingUrl, provider, popupRef.current);
      if (popup) {
        popupRef.current = popup;
        startPollPopup(popup);
        setTimeout(() => {
          setState("active");
          onMeetingStarted();
        }, 600);
      } else {
        // Popup blocker active — open in tab as last resort
        window.open(meetingUrl, "_blank", "noopener,noreferrer");
        setState("active");
        onMeetingStarted();
      }
    }
  }, [meetingUrl, config, iframeBlocked, provider, onMeetingStarted, startPollPopup]);

  const reconnect = useCallback(() => {
    if (!meetingUrl) return;
    const popup = openMeetingPopup(meetingUrl, provider, popupRef.current);
    if (popup) {
      popupRef.current = popup;
      startPollPopup(popup);
      setState("active");
    }
  }, [meetingUrl, provider, startPollPopup]);

  const copyLink = useCallback(async () => {
    if (!meetingUrl) return;
    await navigator.clipboard.writeText(meetingUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [meetingUrl]);

  const openExternal = useCallback(() => {
    if (meetingUrl) window.open(meetingUrl, "_blank", "noopener,noreferrer");
  }, [meetingUrl]);

  // Embed URL for iframe mode
  const embedUrl = config.canEmbed && meetingUrl ? config.getEmbedUrl(meetingUrl) : null;
  const renderIframe = state === "active" && joinMode === "iframe" && !!embedUrl && !iframeBlocked;

  // ── No meeting link ────────────────────────────────────────────────────

  if (!meetingUrl) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-3 max-w-xs">
          <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto text-2xl">📹</div>
          <p className="text-sm font-medium text-gray-600">No meeting link configured</p>
          <p className="text-xs text-gray-400">Add a meeting URL when scheduling the interview to enable this panel.</p>
        </div>
      </div>
    );
  }

  // ── Full layout ────────────────────────────────────────────────────────

  return (
    <div className={`flex flex-col bg-gray-50 ${isFullscreen ? "fixed inset-0 z-50" : "h-full"}`}>
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-200 shrink-0">
        <ProviderBadge provider={provider} />
        {state === "active" && <ActivePulse />}
        <div className="ml-auto flex items-center gap-1">
          {state === "active" && (
            <button
              onClick={() => void copyLink()}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <Copy className="w-3.5 h-3.5" />
              {copied ? "Copied!" : "Copy link"}
            </button>
          )}
          <button
            onClick={openExternal}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Open in tab
          </button>
          <button
            onClick={() => setIsFullscreen((f) => !f)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
            aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 min-h-0 relative overflow-hidden">

        {/* ─ not_started ─ */}
        {state === "not_started" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-5 max-w-xs w-full">
              <div
                className="w-24 h-24 rounded-3xl flex items-center justify-center text-4xl mx-auto shadow-sm"
                style={{ backgroundColor: config.bgColor }}
              >
                {provider === "google_meet" ? "📗" : provider === "teams" ? "🟣" : provider === "zoom" ? "🔵" : "📹"}
              </div>
              <div className="space-y-1.5">
                <p className="text-base font-semibold text-gray-900">{config.displayName}</p>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {config.canEmbed
                    ? "Meeting will open inside this panel."
                    : "Meeting will open in a popup window. Your notes and controls stay available here."}
                </p>
              </div>
              <Button
                className="w-full h-10 text-white font-medium"
                style={{ backgroundColor: config.color }}
                onClick={joinMeeting}
              >
                Join Meeting
              </Button>
              {!config.canEmbed && (
                <p className="text-[10px] text-gray-400">
                  {config.displayName} restricts embedding — a popup keeps AIRIS workspace fully visible alongside the call.
                </p>
              )}
            </div>
          </div>
        )}

        {/* ─ connecting ─ */}
        {state === "connecting" && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-3">
              <div
                className="w-10 h-10 rounded-full border-[3px] border-t-transparent animate-spin mx-auto"
                style={{ borderColor: `${config.color}66`, borderTopColor: config.color }}
              />
              <p className="text-sm text-gray-500">Connecting to {config.displayName}…</p>
            </div>
          </div>
        )}

        {/* ─ active — iframe mode ─ */}
        {renderIframe && (
          <iframe
            src={embedUrl!}
            className="w-full h-full border-0"
            allow="camera; microphone; fullscreen; display-capture; autoplay; speaker-selection"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals"
            title={`${config.displayName} meeting`}
            onError={() => {
              setIframeBlocked(true);
              reconnect();
            }}
          />
        )}

        {/* ─ active — popup mode ─ */}
        {state === "active" && joinMode === "popup" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-5 max-w-sm w-full">
              <div
                className="w-24 h-24 rounded-3xl flex items-center justify-center text-4xl mx-auto shadow-sm ring-4 ring-green-200"
                style={{ backgroundColor: config.bgColor }}
              >
                {provider === "google_meet" ? "📗" : provider === "teams" ? "🟣" : "🔵"}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-2">
                  <Wifi className="w-4 h-4 text-green-500" />
                  <p className="text-sm font-semibold text-gray-900">Meeting is active</p>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {config.displayName} is running in your popup window.
                  Your interview notes and controls are available in the right panel.
                </p>
              </div>
              <div className="flex gap-2 justify-center">
                <button
                  onClick={reconnect}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-700 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reopen popup
                </button>
                <button
                  onClick={openExternal}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-700 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open in tab
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ─ disconnected ─ */}
        {state === "disconnected" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-4 max-w-xs w-full">
              <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mx-auto">
                <WifiOff className="w-8 h-8 text-red-400" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-gray-800">Meeting window closed</p>
                <p className="text-xs text-gray-400">Reopen the popup or open in a browser tab to continue.</p>
              </div>
              <div className="flex gap-2 justify-center">
                <Button variant="outline" className="gap-1.5 text-xs h-8" onClick={reconnect}>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reconnect
                </Button>
                <Button variant="outline" className="gap-1.5 text-xs h-8" onClick={openExternal}>
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open in tab
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ─ completed ─ */}
        {state === "completed" && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center space-y-3 max-w-xs w-full">
              <div className="w-16 h-16 rounded-2xl bg-green-50 flex items-center justify-center mx-auto text-3xl">
                ✓
              </div>
              <p className="text-sm font-semibold text-gray-800">Interview session ended</p>
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
