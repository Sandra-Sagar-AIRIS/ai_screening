/**
 * LiveKit API helpers.
 *
 * Fetches a short-lived access token from the AIRIS backend.
 * The token grants the current user permission to join the interview's
 * dedicated LiveKit room.  All media flows directly between the browser
 * and the LiveKit server — the backend is only involved in token issuance.
 */

import { apiRequest } from "./client";

export type LiveKitTokenResponse = {
  token: string;
  ws_url: string;
  room_name: string;
  identity: string;
};

/**
 * Request a LiveKit participant token for the given interview.
 * Caching is intentionally disabled (TTL=0) — tokens are time-sensitive
 * and must always be fresh when the user joins or re-joins the meeting.
 */
export async function getLiveKitToken(
  interviewId: string,
): Promise<LiveKitTokenResponse> {
  return apiRequest<LiveKitTokenResponse>(
    `/interviews/${interviewId}/livekit/token`,
    { method: "POST" },
    0, // no cache — tokens must always be fresh
  );
}

/**
 * Request a guest LiveKit token for a candidate to join the meeting.
 * No authentication required — open endpoint keyed only by the interview UUID.
 */
export async function getLiveKitGuestToken(
  interviewId: string,
  name: string,
): Promise<LiveKitTokenResponse> {
  return apiRequest<LiveKitTokenResponse>(
    `/interviews/${interviewId}/livekit/guest-token`,
    {
      method: "POST",
      body: JSON.stringify({ name }),
    },
    0,
  );
}
