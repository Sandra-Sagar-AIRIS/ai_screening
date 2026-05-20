"use client";

/**
 * PIPE-007: Conversion Funnel Chart
 *
 * Pure-CSS funnel visualization — no external charting library required.
 * Each stage bar is proportional to `entered`, with a coloured overlay
 * showing how many advanced vs. were rejected.
 */

import type { StageFunnelEntry } from "@/lib/api/types";

const STAGE_COLORS: Record<string, { bar: string; advanced: string; rejected: string }> = {
  applied:     { bar: "bg-violet-100", advanced: "bg-violet-500", rejected: "bg-red-400" },
  screening:   { bar: "bg-sky-100",    advanced: "bg-sky-500",    rejected: "bg-red-400" },
  ai_screening:{ bar: "bg-orange-100", advanced: "bg-orange-500", rejected: "bg-red-400" },
  interview:   { bar: "bg-emerald-100",advanced: "bg-emerald-500",rejected: "bg-red-400" },
  offer:       { bar: "bg-amber-100",  advanced: "bg-amber-500",  rejected: "bg-red-400" },
  placed:      { bar: "bg-teal-100",   advanced: "bg-teal-500",   rejected: "bg-red-400" },
};

const DEFAULT_COLOR = { bar: "bg-slate-100", advanced: "bg-slate-400", rejected: "bg-red-400" };

interface ConversionFunnelChartProps {
  funnel: StageFunnelEntry[];
}

export function ConversionFunnelChart({ funnel }: ConversionFunnelChartProps) {
  if (funnel.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 italic">
        No pipeline data available for the selected filters.
      </p>
    );
  }

  const maxEntered = Math.max(...funnel.map((f) => f.entered), 1);

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex items-center gap-4 text-[11px] text-slate-500 pb-1">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-5 rounded-sm bg-emerald-500 inline-block" />
          Advanced
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-5 rounded-sm bg-red-400 inline-block" />
          Rejected
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-5 rounded-sm bg-slate-200 inline-block" />
          Still in stage
        </span>
      </div>

      {funnel.map((entry) => {
        const colors = STAGE_COLORS[entry.stage] ?? DEFAULT_COLOR;
        const barWidth = entry.entered > 0 ? (entry.entered / maxEntered) * 100 : 0;
        const advancedPct = entry.entered > 0 ? (entry.advanced / entry.entered) * 100 : 0;
        const rejectedPct = entry.entered > 0 ? (entry.rejected / entry.entered) * 100 : 0;
        const stillPct = entry.entered > 0 ? (entry.still_in_stage / entry.entered) * 100 : 0;

        return (
          <div key={entry.stage} className="group">
            {/* Stage label row */}
            <div className="flex items-center justify-between mb-1">
              <span className="text-[13px] font-semibold text-slate-700">{entry.label}</span>
              <div className="flex items-center gap-3 text-[12px] text-slate-500">
                <span>
                  <span className="font-bold text-slate-800">{entry.entered.toLocaleString()}</span> entered
                </span>
                <span className="text-emerald-600 font-semibold">
                  {entry.conversion_rate}% advanced
                </span>
                {entry.rejection_rate > 0 && (
                  <span className="text-red-500 font-semibold">
                    {entry.rejection_rate}% rejected
                  </span>
                )}
              </div>
            </div>

            {/* Bar */}
            <div className="relative h-8 rounded-lg overflow-hidden bg-slate-100" style={{ width: "100%" }}>
              {/* Scale the bar width proportional to max entered */}
              <div
                className="absolute left-0 top-0 h-full rounded-lg overflow-hidden flex"
                style={{ width: `${barWidth}%` }}
              >
                {/* Advanced portion */}
                <div
                  className={`h-full ${colors.advanced} transition-all duration-500`}
                  style={{ width: `${advancedPct}%` }}
                  title={`Advanced: ${entry.advanced.toLocaleString()}`}
                />
                {/* Rejected portion */}
                <div
                  className="h-full bg-red-400 transition-all duration-500"
                  style={{ width: `${rejectedPct}%` }}
                  title={`Rejected: ${entry.rejected.toLocaleString()}`}
                />
                {/* Still in stage portion */}
                <div
                  className="h-full bg-slate-300 transition-all duration-500"
                  style={{ width: `${stillPct}%` }}
                  title={`Still in stage: ${entry.still_in_stage.toLocaleString()}`}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
