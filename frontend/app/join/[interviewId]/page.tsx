"use client";

/**
 * Candidate Interview Join Page — /join/[interviewId]
 *
 * Public page (no AIRIS account required). The recruiter copies this URL
 * and sends it to the candidate. The candidate enters their name and joins
 * the embedded LiveKit video session directly in the browser.
 *
 * Token is issued by POST /interviews/{id}/livekit/guest-token — no auth required.
 * The interview UUID acts as an unguessable room secret.
 */

import { FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  Room,
  RoomEvent,
  Track,
  VideoPresets,
  createLocalAudioTrack,
  createLocalVideoTrack,
  setLogLevel,
} from "livekit-client";
import {
  Loader2,
  Mic,
  MicOff,
  PhoneOff,
  Video,
  VideoOff,
  WifiOff,
} from "lucide-react";
import { getLiveKitGuestToken } from "@/lib/api/livekit";
import { ApiError } from "@/lib/api/client";

setLogLevel("silent");

// ── Small video tile (reused pattern from LiveKitRoom) ───────────────────────

function VideoTile({ track, label, muted }: { track: Track; label: string; muted: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    track.attach(el);
    return () => { track.detach(el); };
  }, [track]);
  return (
    <div className="relative bg-gray-800 rounded-lg overflow-hidden flex-1 min-h-0">
      <video ref={ref} autoPlay playsInline muted={muted} className="w-full h-full object-cover" />
      <span className="absolute bottom-2 left-2 text-[10px] font-medium text-white/80 bg-black/40 px-1.5 py-0.5 rounded">
        {label}
      </span>
    </div>
  );
}

function AudioTrack({ track }: { track: Track }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    track.attach(el);
    return () => { track.detach(el); };
  }, [track]);
  return <audio ref={ref} autoPlay playsInline className="hidden" />;
}

// ── Types ─────────────────────────────────────────────────────────────────────

type Phase = "form" | "connecting" | "connected" | "disconnected" | "error" | "unavailable";

type VideoEntry = { trackSid: string; track: Track; label: string; isLocal: boolean };

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CandidateJoinPage() {
  const params = useParams();
  const interviewId = params.interviewId as string;

  const [phase, setPhase] = useState<Phase>("form");
  const [name, setName] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const [camOn, setCamOn] = useState(false);
  const [micOn, setMicOn] = useState(false);
  const [videoEntries, setVideoEntries] = useState<VideoEntry[]>([]);
  const [audioTracks, setAudioTracks] = useState<Track[]>([]);

  const roomRef = useRef<Room | null>(null);

  // ── Track helpers ───────────────────────────────────────────────────────────

  function rebuildTracks(room: Room) {
    const vids: VideoEntry[] = [];
    const auds: Track[] = [];

    room.localParticipant.videoTrackPublications.forEach((pub) => {
      if (pub.track?.kind === Track.Kind.Video) {
        vids.push({ trackSid: pub.trackSid, track: pub.track, label: "You", isLocal: true });
      }
    });

    room.remoteParticipants.forEach((p) => {
      p.trackPublications.forEach((pub) => {
        if (!pub.track) return;
        if (pub.track.kind === Track.Kind.Video) {
          vids.push({ trackSid: pub.trackSid, track: pub.track, label: p.name ?? "Interviewer", isLocal: false });
        } else if (pub.track.kind === Track.Kind.Audio) {
          auds.push(pub.track);
        }
      });
    });

    setVideoEntries(vids);
    setAudioTracks(auds);
  }

  // ── Connect ─────────────────────────────────────────────────────────────────

  async function connect(displayName: string) {
    setPhase("connecting");
    setErrorMsg("");

    let token: string;
    let wsUrl: string;

    try {
      const data = await getLiveKitGuestToken(interviewId, displayName);
      token = data.token;
      wsUrl = data.ws_url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setPhase("unavailable");
        return;
      }
      if (err instanceof ApiError && err.status === 410) {
        setPhase("error");
        setErrorMsg("This interview session is no longer active.");
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setPhase("error");
        setErrorMsg("Interview not found. Please check the link and try again.");
        return;
      }
      setPhase("error");
      setErrorMsg(err instanceof Error ? err.message : "Could not fetch meeting token.");
      return;
    }

    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      videoCaptureDefaults: { resolution: VideoPresets.h720.resolution },
    });
    roomRef.current = room;

    room
      .on(RoomEvent.TrackSubscribed, () => rebuildTracks(room))
      .on(RoomEvent.TrackUnsubscribed, () => rebuildTracks(room))
      .on(RoomEvent.LocalTrackPublished, () => rebuildTracks(room))
      .on(RoomEvent.LocalTrackUnpublished, () => rebuildTracks(room))
      .on(RoomEvent.ParticipantConnected, () => rebuildTracks(room))
      .on(RoomEvent.ParticipantDisconnected, () => rebuildTracks(room))
      .on(RoomEvent.Disconnected, () => {
        setPhase("disconnected");
      })
      .on(RoomEvent.Connected, () => {
        setPhase("connected");
        rebuildTracks(room);
      });

    try {
      await room.connect(wsUrl, token);
    } catch (err) {
      setPhase("error");
      setErrorMsg(err instanceof Error ? err.message : "Could not connect to meeting.");
    }
  }

  // Disconnect on unmount
  useEffect(() => {
    return () => { roomRef.current?.disconnect(); };
  }, []);

  // ── Media toggles ───────────────────────────────────────────────────────────

  async function toggleMic() {
    const room = roomRef.current;
    if (!room) return;
    if (micOn) {
      room.localParticipant.audioTrackPublications.forEach((pub) => {
        if (pub.source === Track.Source.Microphone) void room.localParticipant.unpublishTrack(pub.track!);
      });
      setMicOn(false);
    } else {
      try {
        await room.localParticipant.publishTrack(await createLocalAudioTrack());
        setMicOn(true);
      } catch { /* denied */ }
    }
  }

  async function toggleCamera() {
    const room = roomRef.current;
    if (!room) return;
    if (camOn) {
      room.localParticipant.videoTrackPublications.forEach((pub) => {
        if (pub.source === Track.Source.Camera) void room.localParticipant.unpublishTrack(pub.track!);
      });
      setCamOn(false);
    } else {
      try {
        await room.localParticipant.publishTrack(await createLocalVideoTrack());
        setCamOn(true);
      } catch { /* denied */ }
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  // ── Name entry form ─────────────────────────────────────────────────────────
  if (phase === "form") {
    function handleSubmit(e: FormEvent) {
      e.preventDefault();
      const trimmed = name.trim();
      if (!trimmed) return;
      void connect(trimmed);
    }

    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm space-y-6">
          {/* Branding */}
          <div className="text-center space-y-1">
            <div className="w-12 h-12 rounded-xl bg-[#FF5A1F] flex items-center justify-center mx-auto text-white font-black text-xl">
              A
            </div>
            <p className="text-xs text-gray-400 font-medium tracking-wide uppercase">AIRIS Interview</p>
          </div>

          <div className="space-y-1 text-center">
            <h1 className="text-lg font-semibold text-gray-900">Join your interview</h1>
            <p className="text-sm text-gray-500">Enter your name to join the video session</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your full name"
              autoFocus
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/40 focus:border-[#FF5A1F]"
            />
            <button
              type="submit"
              disabled={!name.trim()}
              className="w-full h-10 rounded-lg bg-[#FF5A1F] text-white text-sm font-semibold hover:bg-[#e04e18] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Join Meeting
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Connecting ──────────────────────────────────────────────────────────────
  if (phase === "connecting") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center space-y-3 text-white/70">
          <Loader2 className="w-8 h-8 animate-spin mx-auto" />
          <p className="text-sm">Joining the meeting…</p>
        </div>
      </div>
    );
  }

  // ── Error states ────────────────────────────────────────────────────────────
  if (phase === "unavailable") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
        <div className="text-center space-y-4 max-w-xs">
          <WifiOff className="w-10 h-10 text-amber-400 mx-auto" />
          <p className="text-white font-semibold">Video meeting not available</p>
          <p className="text-sm text-white/50">
            The recruiter&apos;s meeting platform isn&apos;t configured yet. Please contact
            your interviewer for an alternative link.
          </p>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
        <div className="text-center space-y-4 max-w-xs">
          <WifiOff className="w-10 h-10 text-red-400 mx-auto" />
          <p className="text-white font-semibold">Could not join meeting</p>
          <p className="text-sm text-white/50">{errorMsg}</p>
          <button
            onClick={() => setPhase("form")}
            className="text-sm px-4 py-2 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (phase === "disconnected") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
        <div className="text-center space-y-4 max-w-xs">
          <div className="w-14 h-14 rounded-2xl bg-amber-900/40 flex items-center justify-center mx-auto text-3xl">🔌</div>
          <p className="text-white font-semibold">You&apos;ve left the meeting</p>
          <p className="text-sm text-white/50">The interview session has ended.</p>
          <button
            onClick={() => setPhase("form")}
            className="text-sm px-4 py-2 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors"
          >
            Rejoin
          </button>
        </div>
      </div>
    );
  }

  // ── Connected — meeting room ─────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="w-6 h-6 rounded bg-[#FF5A1F] flex items-center justify-center text-white font-black text-xs">A</div>
        <span className="text-sm font-medium text-white/80">AIRIS Interview</span>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-green-400">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live
        </span>
      </div>

      {/* Video grid */}
      <div className="flex-1 min-h-0 p-3 flex gap-3">
        {videoEntries.length > 0 ? (
          videoEntries.map((e) => (
            <VideoTile key={e.trackSid} track={e.track} label={e.label} muted={e.isLocal} />
          ))
        ) : (
          <div className="flex-1 flex items-center justify-center text-white/30 text-sm">
            Waiting for video…
          </div>
        )}
      </div>

      {/* Hidden audio */}
      {audioTracks.map((t) => <AudioTrack key={t.sid} track={t} />)}

      {/* Controls */}
      <div className="shrink-0 flex items-center justify-center gap-3 px-4 py-3 bg-gray-800 border-t border-gray-700">
        <button
          onClick={() => void toggleMic()}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors ${micOn ? "bg-gray-700 text-white" : "bg-red-500/20 text-red-400"}`}
          title={micOn ? "Mute" : "Unmute"}
        >
          {micOn ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
          <span className="text-[9px]">{micOn ? "Mute" : "Unmuted"}</span>
        </button>

        <button
          onClick={() => void toggleCamera()}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors ${camOn ? "bg-gray-700 text-white" : "bg-red-500/20 text-red-400"}`}
          title={camOn ? "Stop camera" : "Start camera"}
        >
          {camOn ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
          <span className="text-[9px]">{camOn ? "Camera" : "Camera off"}</span>
        </button>

        <button
          onClick={() => roomRef.current?.disconnect()}
          className="flex flex-col items-center gap-1 px-3 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white transition-colors"
          title="Leave meeting"
        >
          <PhoneOff className="w-5 h-5" />
          <span className="text-[9px]">Leave</span>
        </button>
      </div>
    </div>
  );
}
