"use client";

import { Button } from "@/components/ui/button";
import type { JobVendorAssignment } from "@/lib/api/types";

export type VendorListProps = {
  vendors: JobVendorAssignment[];
  canRemove: boolean;
  /** When true, all remove actions are disabled (e.g. another vendor mutation in progress). */
  lockActions?: boolean;
  removingId: string | null;
  onRemove: (vendorId: string) => void;
};

export function VendorList({ vendors, canRemove, lockActions, removingId, onRemove }: VendorListProps) {
  if (vendors.length === 0) {
    return <p className="text-sm text-slate-600">No vendors assigned yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className="p-3 font-medium text-slate-700">Vendor</th>
            {canRemove ? <th className="p-3 font-medium text-slate-700">Action</th> : null}
          </tr>
        </thead>
        <tbody>
          {vendors.map((v) => (
            <tr key={v.vendor_id} className="border-b border-slate-100 last:border-0">
              <td className="p-3 text-slate-900">{v.email}</td>
              {canRemove ? (
                <td className="p-3">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-8 px-3 text-xs"
                    disabled={Boolean(lockActions || removingId !== null)}
                    onClick={() => onRemove(v.vendor_id)}
                  >
                    {removingId === v.vendor_id ? "Removing…" : "Remove"}
                  </Button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
