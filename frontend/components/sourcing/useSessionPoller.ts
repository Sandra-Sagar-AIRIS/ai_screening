"use client";

import { useCallback, useEffect, useRef } from "react";
import { pollSessionStatus, type SessionStatusResponse, type SourcingSessionStatus } from "@/lib/api/sourcing";

const TERMINAL_STATUSES: SourcingSessionStatus[] = ["complete", "failed"];
const POLL_INTERVAL_MS = 2000;

/**
 * Polls session status every 2s while the session is running.
 * Stops automatically when the status becomes terminal (complete/failed).
 * Cleans up on unmount.
 */
export function useSessionPoller(
  sessionId: string | null,
  onUpdate: (status: SessionStatusResponse) => void,
): void {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const activeRef = useRef(true);

  useEffect(() => {
    if (!sessionId) return;
    activeRef.current = true;

    let timeoutId: ReturnType<typeof setTimeout>;

    async function tick() {
      if (!activeRef.current) return;
      try {
        const status = await pollSessionStatus(sessionId!);
        if (!activeRef.current) return;
        onUpdateRef.current(status);
        if (!TERMINAL_STATUSES.includes(status.status)) {
          timeoutId = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch {
        // On network error, keep polling
        if (activeRef.current) {
          timeoutId = setTimeout(tick, POLL_INTERVAL_MS * 2);
        }
      }
    }

    void tick();

    return () => {
      activeRef.current = false;
      clearTimeout(timeoutId);
    };
  }, [sessionId]);
}
