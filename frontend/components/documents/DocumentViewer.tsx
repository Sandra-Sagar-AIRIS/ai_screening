"use client";

import type { ReactNode } from "react";

export function DocumentViewer(props: {
  fileTitle: string;
  fileSubtitle: string;
  icon: ReactNode;
  /** Shown when state is empty or unsupported */
  helper?: ReactNode;
  error?: string | null;
  loading?: boolean;
}) {
  const { fileTitle, fileSubtitle, icon, helper, error, loading } = props;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-[#FF5A1F]">
            {icon}
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">{fileTitle}</p>
            <p className="text-xs text-gray-500">{fileSubtitle}</p>
            {loading ? <p className="mt-1 text-xs font-medium text-[#FF5A1F]">Loading…</p> : null}
            {error ? <p className="mt-1 text-xs font-medium text-red-600">{error}</p> : null}
            {helper ? <div className="mt-2 text-xs text-gray-600">{helper}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
