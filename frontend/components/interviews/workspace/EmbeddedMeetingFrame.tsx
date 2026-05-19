"use client";

/**
 * EmbeddedMeetingFrame
 *
 * Isolated iframe wrapper for embeddable meeting providers (Zoom /wc/, generic URLs).
 *
 * Responsibilities:
 *  - Render the iframe with the correct permissions and sandbox flags
 *  - Detect when the browser blocks the frame (X-Frame-Options / CSP)
 *  - Report load / blocked state upward via callbacks
 *  - Prevent memory leaks: the iframe is keyed so React fully unmounts/remounts
 *    on URL change rather than mutating the src in place
 *
 * NOTE: Google Meet and Microsoft Teams send X-Frame-Options headers that
 * unconditionally prevent iframe embedding from any cross-origin page.
 * This component is only used when the provider config sets canEmbed=true.
 */

import { memo, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

type EmbedState = "loading" | "ready" | "blocked";

export const EmbeddedMeetingFrame = memo(function EmbeddedMeetingFrame({
  src,
  title,
  onReady,
  onBlocked,
}: {
  /** The embeddable URL (already transformed by provider's getEmbedUrl). */
  src: string;
  title: string;
  onReady?: () => void;
  onBlocked?: () => void;
}) {
  const [embedState, setEmbedState] = useState<EmbedState>("loading");
  const iframeRef = useRef<HTMLIFrameElement>(null);
  // Track whether we have received any signal from the iframe.
  const loadedRef = useRef(false);

  // The iframe fires `onLoad` when the document inside it loads successfully.
  // If the browser blocks the frame (X-Frame-Options), the `load` event still
  // fires but `contentDocument` is null or an opaque object — we can't read it
  // directly due to cross-origin restrictions.  Instead we use a heuristic:
  // after a generous timeout, if `onLoad` hasn't fired, we assume blocked.
  useEffect(() => {
    loadedRef.current = false;
    setEmbedState("loading");

    const timeout = window.setTimeout(() => {
      if (!loadedRef.current) {
        setEmbedState("blocked");
        onBlocked?.();
      }
    }, 8000); // 8s — enough for slow connections, short enough to be responsive

    return () => window.clearTimeout(timeout);
  }, [src, onBlocked]);

  function handleLoad() {
    loadedRef.current = true;
    setEmbedState("ready");
    onReady?.();
  }

  function handleError() {
    setEmbedState("blocked");
    onBlocked?.();
  }

  return (
    <div className="relative w-full h-full bg-gray-900">
      {/* Loading overlay — hidden once iframe fires onLoad */}
      {embedState === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
          <div className="flex flex-col items-center gap-3 text-white/70">
            <Loader2 className="w-8 h-8 animate-spin" />
            <p className="text-sm">Connecting to meeting…</p>
          </div>
        </div>
      )}

      {/* The meeting iframe — always in the DOM so it starts loading immediately */}
      <iframe
        key={src}
        ref={iframeRef}
        src={src}
        title={title}
        className={`w-full h-full border-0 transition-opacity duration-300 ${
          embedState === "ready" ? "opacity-100" : "opacity-0"
        }`}
        // Camera/mic/display are required for video calls.
        // speaker-selection is needed for audio output device switching.
        allow="camera *; microphone *; fullscreen *; display-capture *; autoplay *; speaker-selection *; clipboard-write *"
        // allow-popups-to-escape-sandbox lets Zoom / generic providers open
        // sub-windows (e.g. screen-share picker) without breaking the session.
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads"
        referrerPolicy="no-referrer-when-downgrade"
        onLoad={handleLoad}
        onError={handleError}
      />
    </div>
  );
});
