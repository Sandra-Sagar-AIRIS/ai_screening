"use client";

import { useEffect, useState } from "react";
import { RoleTable } from "@/components/RoleTable";
import { ApiError } from "@/lib/api/client";
import { getRoles, type Role } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

const ROLE_FLASH_KEY = "airis_role_flash";

function PageLoader() {
  return (
    <div className="flex min-h-[200px] items-center justify-center">
      <p className="text-sm text-slate-600">Loading...</p>
    </div>
  );
}

export default function RolesPage() {
  const role = useAuthStore((state) => state.role);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const flash = sessionStorage.getItem(ROLE_FLASH_KEY);
    if (flash === "created") {
      setSuccessMessage("Role created successfully.");
      sessionStorage.removeItem(ROLE_FLASH_KEY);
    } else if (flash === "updated") {
      setSuccessMessage("Permissions updated successfully.");
      sessionStorage.removeItem(ROLE_FLASH_KEY);
    }
  }, []);

  useEffect(() => {
    async function load() {
      if (role !== "admin") {
        setLoading(false);
        return;
      }

      setError(null);
      try {
        const roleRows = await getRoles();
        setRoles(roleRows);
      } catch (err) {
        if (err instanceof ApiError) {
          setError("Failed to load roles. Please try again.");
        } else {
          setError("Something went wrong. Please try again.");
        }
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [role]);

  if (role !== "admin") {
    return <p className="text-sm text-slate-600">Only admins can manage roles.</p>;
  }

  if (loading) {
    return <PageLoader />;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Roles</h1>
      {successMessage ? (
        <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900" role="status">
          {successMessage}
        </p>
      ) : null}
      <RoleTable roles={roles} error={error} />
    </section>
  );
}
