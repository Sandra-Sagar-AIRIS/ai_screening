import { apiRequest } from "@/lib/api/client";
import type {
  AcceptInvitePayload,
  CreateInvitePayload,
  InviteAcceptResponse,
  InviteCreateResponse,
  InviteListItem,
  InviteResendResponse,
} from "@/lib/api/types";

export async function createInvite(payload: CreateInvitePayload) {
  return apiRequest<InviteCreateResponse>("/invites", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function acceptInvite(payload: AcceptInvitePayload) {
  return apiRequest<InviteAcceptResponse>("/invites/accept", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: false,
  });
}

export async function getInvites() {
  return apiRequest<InviteListItem[]>("/invites");
}

export async function resendInvite(inviteId: string) {
  return apiRequest<InviteResendResponse>(`/invites/${inviteId}/resend`, {
    method: "POST",
  });
}

/**
 * F-INV-05: Mark an invite as 'opened' when the recipient visits the accept page.
 * Fires GET /invites/open?token=<token>. Returns 204. Safe to ignore errors.
 */
export async function openInvite(token: string): Promise<void> {
  try {
    await apiRequest<void>(`/invites/open?token=${encodeURIComponent(token)}`, {
      method: "GET",
      auth: false,
    });
  } catch {
    // Non-critical — lifecycle tracking failure should not block the UI
  }
}
