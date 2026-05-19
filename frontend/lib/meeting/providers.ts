/**
 * Meeting provider abstraction layer.
 *
 * Defines provider metadata used by MeetingContainer to:
 *   - display the correct brand name / colour
 *   - decide whether to attempt iframe embedding
 *   - transform a raw meeting_link into an embeddable URL
 *
 * NO popup logic lives here.  openMeetingPopup() has been removed entirely.
 * MeetingContainer routes non-embeddable providers to the "external" mode
 * which shows a plain <a href> link — no window.open, no popup windows.
 *
 * Provider embedding reality:
 * ─────────────────────────────────────────────────────────────────────────
 * google_meet  X-Frame-Options: SAMEORIGIN → can never be embedded cross-origin
 * teams        X-Frame-Options: DENY       → can never be embedded
 * zoom /wc/    No X-Frame-Options on some endpoints → iframe may work
 * daily.co     Explicitly supports <iframe> embedding via prebuilt UI
 * livekit      JS SDK — NOT an iframe, runs same-origin in React tree
 * other        iframe attempted; falls back to external-link on block
 * ─────────────────────────────────────────────────────────────────────────
 */

export type MeetingProvider =
  | "google_meet"
  | "teams"
  | "zoom"
  | "livekit"   // AIRIS-native embedded via LiveKit React SDK (not iframe)
  | "daily"     // Daily.co — supports first-party <iframe> embedding
  | "other";

export type ProviderConfig = {
  id: MeetingProvider;
  displayName: string;
  /** Primary brand colour (hex). */
  color: string;
  /** Light tint used for backgrounds. */
  bgColor: string;
  /**
   * Whether to attempt iframe embedding.
   * false → MeetingContainer shows external-link Companion Panel immediately.
   * Note: "livekit" is also false here because it uses the JS SDK, not an iframe.
   */
  canEmbed: boolean;
  /**
   * Transform the raw meeting_link into an embeddable URL.
   * Return null if no embed URL is possible.
   */
  getEmbedUrl: (url: string) => string | null;
};

const PROVIDER_CONFIGS: Record<MeetingProvider, ProviderConfig> = {
  // ── AIRIS-native (fully embedded via JS SDK) ──────────────────────────
  livekit: {
    id: "livekit",
    displayName: "AIRIS Meeting",
    color: "#00b87a",
    bgColor: "#e6f9f3",
    // LiveKit uses the JS SDK — not an iframe.  canEmbed=false here so
    // MeetingContainer doesn't try to iframe it; the "livekit" provider
    // branch is handled separately before the iframe/external decision.
    canEmbed: false,
    getEmbedUrl: () => null,
  },

  // ── Future: Daily.co (first-party iframe support) ─────────────────────
  daily: {
    id: "daily",
    displayName: "Daily.co",
    color: "#1b4fff",
    bgColor: "#e8eeff",
    canEmbed: true,
    getEmbedUrl: (url) => url,
  },

  // ── Third-party providers ─────────────────────────────────────────────
  google_meet: {
    id: "google_meet",
    displayName: "Google Meet",
    color: "#1a73e8",
    bgColor: "#e8f0fe",
    // Google Meet sends X-Frame-Options: SAMEORIGIN; embedding from any
    // cross-origin domain (including airis.app) is blocked at browser level.
    // This is a hard security constraint — no workaround exists.
    canEmbed: false,
    getEmbedUrl: () => null,
  },
  teams: {
    id: "teams",
    displayName: "Microsoft Teams",
    color: "#6264a7",
    bgColor: "#f0f0f9",
    // Teams sends X-Frame-Options: DENY globally.
    canEmbed: false,
    getEmbedUrl: () => null,
  },
  zoom: {
    id: "zoom",
    displayName: "Zoom",
    color: "#2D8CFF",
    bgColor: "#e8f4ff",
    // Zoom Web Client (/wc/) omits X-Frame-Options on some endpoints.
    // Embedding may work depending on account settings; falls back to
    // external-link panel if the browser blocks it.
    canEmbed: true,
    getEmbedUrl: (url) => {
      if (/zoom\.us\/wc\//.test(url)) return url;
      const match = url.match(/zoom\.us\/j\/(\d+)/);
      if (match) return `https://zoom.us/wc/${match[1]}/join`;
      return null;
    },
  },
  other: {
    id: "other",
    displayName: "Video Meeting",
    color: "#64748b",
    bgColor: "#f1f5f9",
    canEmbed: true,
    getEmbedUrl: (url) => url,
  },
};

/** Infer the meeting provider from a URL. */
export function detectProvider(url: string): MeetingProvider {
  if (!url) return "other";
  if (/meet\.google\.com/.test(url)) return "google_meet";
  if (/teams\.microsoft\.com|teams\.live\.com/.test(url)) return "teams";
  if (/zoom\.us/.test(url)) return "zoom";
  // AIRIS-native LiveKit rooms (served under /room/ or containing livekit)
  if (/\/room\/|livekit/.test(url)) return "livekit";
  // Daily.co — *.daily.co domains
  if (/\.daily\.co/.test(url)) return "daily";
  return "other";
}

export function getProviderConfig(provider: MeetingProvider): ProviderConfig {
  return PROVIDER_CONFIGS[provider];
}
