import { apiRequest } from "@/lib/api/client";
import type { LoginPayload, MePermissionsResponse, SignupPayload, SignupResponse, TokenResponse } from "@/lib/api/types";

export async function login(payload: LoginPayload) {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: false,
  });
}

export async function signup(payload: SignupPayload) {
  return apiRequest<SignupResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
    auth: false,
  });
}

export async function getMyPermissions() {
  return apiRequest<MePermissionsResponse>("/me/permissions");
}
