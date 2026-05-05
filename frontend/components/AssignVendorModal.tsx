"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError, formatApiErrorForUser } from "@/lib/api/client";
import { getVendors } from "@/lib/api";
import type { OrganizationUser } from "@/lib/api/types";

export type AssignVendorModalProps = {
  open: boolean;
  /** Profile IDs already linked to the job; used to filter the assign list. */
  assignedVendorIds: string[];
  onClose: () => void;
  /** Parent runs optimistic list update and `assignVendorToJob`. */
  onAssign: (vendorId: string, email: string) => Promise<void>;
};

export function AssignVendorModal({ open, assignedVendorIds, onClose, onAssign }: AssignVendorModalProps) {
  const assignedKey = assignedVendorIds.slice().sort().join(",");
  const existingVendorIds = useMemo(
    () => new Set(assignedKey ? assignedKey.split(",") : []),
    [assignedKey]
  );
  const [vendors, setVendors] = useState<OrganizationUser[]>([]);
  const [selected, setSelected] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    async function load() {
      setLoadingList(true);
      setError(null);
      try {
        const list = await getVendors();
        if (!cancelled) {
          setVendors(list);
          const first = list.find((v) => !existingVendorIds.has(v.id));
          setSelected(first?.id ?? "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? formatApiErrorForUser(err) : "Unable to load vendor users.");
        }
      } finally {
        if (!cancelled) {
          setLoadingList(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, assignedKey, existingVendorIds]);

  if (!open) {
    return null;
  }

  const available = vendors.filter((v) => !existingVendorIds.has(v.id));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) {
      return;
    }
    const opt = vendors.find((v) => v.id === selected);
    setSubmitting(true);
    setError(null);
    try {
      await onAssign(selected, opt?.email ?? "");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? formatApiErrorForUser(err) : "Unable to assign vendor.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-lg">
        <h2 className="text-lg font-semibold text-slate-900">Assign vendor</h2>
        <p className="mt-1 text-sm text-slate-600">Choose a vendor user for this job.</p>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          {loadingList ? (
            <p className="text-sm text-slate-600">Loading vendors…</p>
          ) : available.length === 0 ? (
            <p className="text-sm text-slate-600">No available vendors to assign (all may already be on this job).</p>
          ) : (
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Vendor</span>
              <select
                className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-slate-900"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                disabled={submitting}
              >
                {available.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.email}
                  </option>
                ))}
              </select>
            </label>
          )}

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || loadingList || available.length === 0 || !selected}>
              {submitting ? "Assigning…" : "Assign"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
