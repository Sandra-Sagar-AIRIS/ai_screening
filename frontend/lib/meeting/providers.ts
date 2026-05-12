/**
 * Meeting provider abstraction layer.
 *
 * Handles provider detection, embed URL transformation, and popup launch.
 * Designed to be extended with Daily.co, Twilio, Agora, or AIRIS-native
 * conferencing without touching call-site code.
 *
 * Reality of iframe embedding:
 * - Google Meet: X-Frame-Options SAMEORIGIN → iframe blocked in cross-origin context → popup
 * - Microsoft Teams: X-Frame-Options DENY → iframe always blocked → popup
 * - Zoom web client (/wc/): no X-Frame-Options on some endpoints → iframe may work
 * - Generic/other: iframe attempted; fallback to popup on error
 */

export type MeetingProvider =
  | "google_meet"
  | "teams"
  | "zoom"
  | "other";

export type ProviderConfig = {
  id: MeetingProvider;
  displayName: string;
  /** Primary brand colour (hex). */
  color: string;
  /** Light tint used for backgrounds. */
  bgColor: string;
  /** Whether to attempt iframe embedding before falling back to popup. */
  canEmbed: boolean;
  /**
   * Transform the raw meeting_link into an embeddable URL.
   * Return null if no embed URL is possible.
   */
  getEmbedUrl: (url: string) => string | null;
  popupWidth: number;
  popupHeight: number;
};

const PROVIDER_CONFIGS: Record<MeetingProvider, ProviderConfig> = {
  google_meet: {
    id: "google_meet",
    displayName: "Google Meet",
    color: "#1a73e8",
    bgColor: "#e8f0fe",
    // Google Meet sends X-Frame-Options: SAMEORIGIN; embedding from a
    // different origin (airis.app) is blocked at the browser level.
    canEmbed: false,
    getEmbedUrl: () => null,
    popupWidth: 1280,
    popupHeight: 800,
  },
  teams: {
    id: "teams",
    displayName: "Microsoft Teams",
    color: "#6264a7",
    bgColor: "#f0f0f9",
    // Teams sends X-Frame-Options: DENY globally; no embed path exists
    // without the Teams JavaScript SDK (requires tenant app registration).
    canEmbed: false,
    getEmbedUrl: () => null,
    popupWidth: 1280,
    popupHeight: 800,
  },
  zoom: {
    id: "zoom",
    displayName: "Zoom",
    color: "#2D8CFF",
    bgColor: "#e8f4ff",
    // Zoom Web Client (/wc/) omits X-Frame-Options on some endpoints;
    // embedding may work depending on account settings and browser policy.
    canEmbed: true,
    getEmbedUrl: (url) => {
      // Already a web-client URL — use directly.
      if (/zoom\.us\/wc\//.test(url)) return url;
      // Convert standard join URL → web client URL.
      const match = url.match(/zoom\.us\/j\/(\d+)/);
      if (match) return `https://zoom.us/wc/${match[1]}/join`;
      return null;
    },
    popupWidth: 1280,
    popupHeight: 800,
  },
  other: {
    id: "other",
    displayName: "Video Meeting",
    color: "#64748b",
    bgColor: "#f1f5f9",
    canEmbed: true,
    getEmbedUrl: (url) => url,
    popupWidth: 1280,
    popupHeight: 800,
  },
};

/** Infer provider from meeting URL. */
export function detectProvider(url: string): MeetingProvider {
  if (!url) return "other";
  if (/meet\.google\.com/.test(url)) return "google_meet";
  if (/teams\.microsoft\.com|teams\.live\.com/.test(url)) return "teams";
  if (/zoom\.us/.test(url)) return "zoom";
  return "other";
}

export function getProviderConfig(provider: MeetingProvider): ProviderConfig {
  return PROVIDER_CONFIGS[provider];
}

/**
 * Open a meeting in a named popup window, centered on screen.
 * Reuses the same window handle if the window is still open (avoids orphan popups).
 */
export function openMeetingPopup(
  url: string,
  provider: MeetingProvider,
  existingWindow: Window | null = null,
): Window | null {
  // Reuse open popup rather than spawning a second one.
  if (existingWindow && !existingWindow.closed) {
    existingWindow.focus();
    return existingWindow;
  }

  const { popupWidth, popupHeight } = PROVIDER_CONFIGS[provider];
  const left = Math.round(window.screenX + (window.outerWidth - popupWidth) / 2);
  const top = Math.round(window.screenY + (window.outerHeight - popupHeight) / 2);

  return window.open(
    url,
    "airis_meeting_window",
    [
      `width=${popupWidth}`,
      `height=${popupHeight}`,
      `left=${left}`,
      `top=${top}`,
      "scrollbars=yes",
      "resizable=yes",
      "toolbar=no",
      "menubar=no",
      "location=yes",
    ].join(","),
  );
}
