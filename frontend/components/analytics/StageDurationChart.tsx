"use client";

/**
 * PIPE-007: Stage Duration Chart
 *
 * Horizontal bar chart showing average days per stage.
 * Slow stages (is_slow=true) are highlighted in amber.
 */

import { AlertTriangle } from "lucide-react";
import type { StageDurationEntry } from "@/lib/api/types";

interface StageDurationChartProps {
  durations: StageDurationEntry[];
}

export function StageDurationChart({ durations }: StageDurationChartProps) {
  if (durations.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 italic">
        No completed stage transitions yet.
      </p>
    );
  }

  const maxDays = Math.max(...durations.map((d) => d.avg_days), 1);

  return (
    <div className="space-y-4">
      {durations.map((entry) => {
        const barPct = (entry.avg_days / maxDays) * 100;
        const barColor = entry.is_slow
          ? "bg-amber-400"
          : "bg-sky-500";
        const textColor = entry.is_slow ? "text-amber-600" : "text-sky-700";

        return (
          <div key={entry.stage} className="group">
            {/* Label row */}
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-slate-700">
                  {entry.label}
                </span>
                {entry.is_slow && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[10px] font-bold text-amber-600 uppercase tracking-wide">
                    <AlertTriangle className="h-2.5 w-2.5" />
                    Slow
                  </span>
                )}
              </div>
              <div className="text-right text-[12px]">
                <span className={`font-bold ${textColor}`}>
                  {entry.avg_days.toFixed(1)}d avg
                </span>
                {entry.median_days !== null && (
                  <span className="ml-2 text-slate-400">
                    {entry.median_days.toFixed(1)}d median
                  </span>
                )}
                <span className="ml-2 text-slate-400 text-[11px]">
                  ({entry.sample_count.toLocaleString()} obs)
                </span>
              </div>
            </div>

            {/* Horizontal bar */}
            <div className="h-6 w-full bg-slate-100 rounded-lg overflow-hidden">
              <div
                className={`h-full ${barColor} rounded-lg transition-all duration-500`}
                style={{ width: `${barPct}%` }}
              />
            </div>
          </div>
        );
      })}

      <p className="text-[11px] text-slate-400 pt-1">
        Based on completed stage transitions only. Active (in-progress) stages are not included.
      </p>
    </div>
  );
}
