"use client";

/**
 * PIPE-007: Drop-off Insights Panel
 *
 * Shows per-stage rejection rates ranked by severity.
 * The bottleneck stage (highest drop-off) is visually highlighted.
 */

import { AlertOctagon, TrendingDown } from "lucide-react";
import type { DropOffEntry } from "@/lib/api/types";

interface DropoffInsightsPanelProps {
  dropOff: DropOffEntry[];
}

function rateColor(rate: number): string {
  if (rate >= 50) return "text-red-600";
  if (rate >= 30) return "text-orange-500";
  if (rate >= 15) return "text-amber-500";
  return "text-slate-500";
}

function rateBarColor(rate: number): string {
  if (rate >= 50) return "bg-red-500";
  if (rate >= 30) return "bg-orange-400";
  if (rate >= 15) return "bg-amber-400";
  return "bg-slate-300";
}

export function DropoffInsightsPanel({ dropOff }: DropoffInsightsPanelProps) {
  if (dropOff.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 italic">
        No rejections recorded in the selected period.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {dropOff.map((entry) => (
        <div
          key={entry.stage}
          className={`relative rounded-xl border p-4 transition-all ${
            entry.is_bottleneck
              ? "border-red-200 bg-red-50/50"
              : "border-slate-100 bg-white"
          }`}
        >
          {/* Bottleneck badge */}
          {entry.is_bottleneck && (
            <div className="absolute -top-2.5 left-4 flex items-center gap-1 rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wide shadow-sm">
              <AlertOctagon className="h-2.5 w-2.5" />
              Bottleneck
            </div>
          )}

          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                #{entry.rank}
              </span>
              <span className="text-[14px] font-semibold text-slate-800">
                {entry.label}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingDown className={`h-3.5 w-3.5 ${rateColor(entry.drop_off_rate)}`} />
              <span className={`text-[15px] font-bold ${rateColor(entry.drop_off_rate)}`}>
                {entry.drop_off_rate.toFixed(1)}%
              </span>
              <span className="text-[12px] text-slate-400">
                drop-off ({entry.rejected_count.toLocaleString()} rejected)
              </span>
            </div>
          </div>

          {/* Drop-off rate bar */}
          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full ${rateBarColor(entry.drop_off_rate)} rounded-full transition-all duration-500`}
              style={{ width: `${Math.min(entry.drop_off_rate, 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
