"use client";

import { create } from "zustand";
import type { UserRole } from "@/lib/api/types";

const TOKEN_KEY = "airis_access_token";
const ROLE_KEY = "airis_user_role";
const ORG_ID_KEY = "airis_organization_id";

type AuthState = {
  token: string | null;
  role: UserRole | null;
  organizationId: string | null;
  setAuth: (token: string, role: UserRole, organizationId: string) => void;
  clearToken: () => void;
  hydrate: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  role: null,
  organizationId: null,
  setAuth: (token, role, organizationId) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(ROLE_KEY, role);
      window.localStorage.setItem(ORG_ID_KEY, organizationId);
    }
    set({ token, role, organizationId });
  },
  clearToken: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(ROLE_KEY);
      window.localStorage.removeItem(ORG_ID_KEY);
    }
    set({ token: null, role: null, organizationId: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") {
      return;
    }
    const token = window.localStorage.getItem(TOKEN_KEY);
    const role = window.localStorage.getItem(ROLE_KEY) as UserRole | null;
    const organizationId = window.localStorage.getItem(ORG_ID_KEY);
    set({ token, role, organizationId });
  },
}));
