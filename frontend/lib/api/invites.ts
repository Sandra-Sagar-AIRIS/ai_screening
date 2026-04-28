import { apiRequest } from "@/lib/api/client";
import type {
  AcceptInvitePayload,
  CreateInvitePayload,
  InviteAcceptResponse,
  InviteCreateResponse,
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
