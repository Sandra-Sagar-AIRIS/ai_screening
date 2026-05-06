"use client";

import { create } from "zustand";
import { getMyPermissions } from "@/lib/api/auth";
import type { Permission, UserRole, UserType } from "@/lib/api/types";

const TOKEN_KEY = "airis_access_token";
const ROLE_KEY = "airis_user_role";
const USER_TYPE_KEY = "airis_user_type";
const ORG_ID_KEY = "airis_organization_id";
const PERMISSIONS_KEY = "airis_permissions";

type AuthState = {
  hydrated: boolean;
  token: string | null;
  role: UserRole | null;
  userType: UserType | null;
  permissions: Permission[];
  organizationId: string | null;
  setAuth: (
    token: string,
    role: UserRole,
    userType: UserType,
    organizationId: string,
    permissions: Permission[]
  ) => void;
  clearToken: () => void;
  hydrate: () => void;
  /** Refetch permissions from API (fixes stale localStorage after backend seeding / role changes). */
  refreshPermissions: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set) => ({
  hydrated: false,
  token: null,
  role: null,
  userType: null,
  permissions: [],
  organizationId: null,
  setAuth: (token, role, userType, organizationId, permissions) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(ROLE_KEY, role);
      window.localStorage.setItem(USER_TYPE_KEY, userType);
      window.localStorage.setItem(ORG_ID_KEY, organizationId);
      window.localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(permissions));
    }
    set({ token, role, userType, organizationId, permissions });
  },
  clearToken: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(ROLE_KEY);
      window.localStorage.removeItem(USER_TYPE_KEY);
      window.localStorage.removeItem(ORG_ID_KEY);
      window.localStorage.removeItem(PERMISSIONS_KEY);
    }
    set({ token: null, role: null, userType: null, permissions: [], organizationId: null });
  },
  hydrate: () => {
    if (typeof window === "undefined") {
      return;
    }
    const token = window.localStorage.getItem(TOKEN_KEY);
    const role = window.localStorage.getItem(ROLE_KEY) as UserRole | null;
    const userType = window.localStorage.getItem(USER_TYPE_KEY) as UserType | null;
    const organizationId = window.localStorage.getItem(ORG_ID_KEY);
    const rawPermissions = window.localStorage.getItem(PERMISSIONS_KEY);
    const permissions = rawPermissions ? (JSON.parse(rawPermissions) as Permission[]) : [];
    set({ token, role, userType, organizationId, permissions, hydrated: true });
  },
  refreshPermissions: async () => {
    if (typeof window === "undefined") {
      return;
    }
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) {
      return;
    }
    try {
      const data = await getMyPermissions();
      const perms = data.permissions ?? [];
      window.localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(perms));
      if (data.role) {
        window.localStorage.setItem(ROLE_KEY, data.role);
      }
      set((s) => ({
        ...s,
        permissions: perms,
        role: data.role ? data.role : s.role,
      }));
    } catch {
      // Leave existing store; caller may redirect on 401 via API client behavior
    }
  },
}));
