import { API_BASE_URL, apiRequest, getWsApiBase } from "@/lib/api/client";
import type {
  AISuggestion,
  CopilotSession,
  CopilotWsEvent,
  SuggestRequestPayload,
  SuggestionMarkPayload,
  TranscriptSegment,
  TranscriptSegmentPayload,
} from "@/lib/api/types";

const base = (interviewId: string) =>
  `/interviews/${interviewId}/copilot`;

// ── Session ───────────────────────────────────────────────────────────────────

/** Create or retrieve the copilot session for this interview. */
export async function startCopilotSession(
  interviewId: string
): Promise<CopilotSession> {
  return apiRequest<CopilotSession>(`${base(interviewId)}/session`, {
    method: "POST",
  }, 0);
}

/** Get the existing copilot session (throws 404 if not started). */
export async function getCopilotSession(
  interviewId: string
): Promise<CopilotSession> {
  return apiRequest<CopilotSession>(`${base(interviewId)}/session`, {}, 0);
}

// ── Transcript ────────────────────────────────────────────────────────────────

export async function addTranscriptSegment(
  interviewId: string,
  payload: TranscriptSegmentPayload
): Promise<TranscriptSegment> {
  return apiRequest<TranscriptSegment>(`${base(interviewId)}/transcript`, {
    method: "POST",
    body: JSON.stringify(payload),
  }, 0);
}

export async function getTranscript(
  interviewId: string,
  limit = 200,
  offset = 0
): Promise<TranscriptSegment[]> {
  return apiRequest<TranscriptSegment[]>(
    `${base(interviewId)}/transcript?limit=${limit}&offset=${offset}`,
    {},
    0
  );
}

// ── Suggestions ───────────────────────────────────────────────────────────────

/**
 * Trigger AI suggestion generation.
 * Returns immediately (202) — poll getSuggestions() or wait for WS event.
 */
export async function requestSuggestions(
  interviewId: string,
  payload: SuggestRequestPayload = {}
): Promise<{ queued: boolean; session_id: string }> {
  return apiRequest<{ queued: boolean; session_id: string }>(
    `${base(interviewId)}/suggest`,
    {
      method: "POST",
      body: JSON.stringify({ count: 3, ...payload }),
    },
    0
  );
}

export async function getSuggestions(
  interviewId: string,
  includeDismissed = false
): Promise<AISuggestion[]> {
  return apiRequest<AISuggestion[]>(
    `${base(interviewId)}/suggestions?include_dismissed=${includeDismissed}`,
    {},
    0
  );
}

export async function markSuggestion(
  interviewId: string,
  suggestionId: string,
  payload: SuggestionMarkPayload
): Promise<AISuggestion> {
  return apiRequest<AISuggestion>(
    `${base(interviewId)}/suggestions/${suggestionId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    0
  );
}

// ── Summary ───────────────────────────────────────────────────────────────────

/**
 * Trigger post-interview AI summary generation.
 * Returns immediately (202) — poll getCopilotSession() for summary field.
 */
export async function requestSummary(
  interviewId: string,
  force = false
): Promise<{ queued: boolean; session_id: string }> {
  return apiRequest<{ queued: boolean; session_id: string }>(
    `${base(interviewId)}/summarize`,
    {
      method: "POST",
      body: JSON.stringify({ force }),
    },
    0
  );
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

/**
 * Open a WebSocket connection to the copilot real-time channel.
 *
 * Usage:
 *   const ws = openCopilotWs(interviewId, token, {
 *     onEvent: (evt) => { ... },
 *     onClose: () => { ... },
 *   });
 *   // later: ws.close()
 */
export function openCopilotWs(
  interviewId: string,
  token: string,
  handlers: {
    onEvent?: (event: CopilotWsEvent) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (err: Event) => void;
  }
): WebSocket {
  const wsBase = getWsApiBase();
  const url = `${wsBase}/interviews/${interviewId}/copilot/ws?token=${encodeURIComponent(token)}`;
  const ws = new WebSocket(url);

  ws.onopen = () => handlers.onOpen?.();

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data as string) as CopilotWsEvent;
      handlers.onEvent?.(data);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = () => handlers.onClose?.();
  ws.onerror = (err) => handlers.onError?.(err);

  return ws;
}

/** Send a ping to keep the WS alive. */
export function sendWsPing(ws: WebSocket): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "ping" }));
  }
}
