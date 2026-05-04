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
