"use client";

import { useState } from "react";
import { AlertCircle, Briefcase, MapPin, Star, UserCheck, UserX } from "lucide-react";
import type { SourcingResult } from "@/lib/api/sourcing";
import { updateResultAction } from "@/lib/api/sourcing";

// ── Tier colour map ───────────────────────────────────────────────────────────

const TIER_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  Strong:   { bg: "bg-emerald-50",  text: "text-emerald-700", ring: "ring-emerald-200" },
  Good:     { bg: "bg-blue-50",     text: "text-blue-700",    ring: "ring-blue-200"    },
  Moderate: { bg: "bg-amber-50",    text: "text-amber-700",   ring: "ring-amber-200"   },
  Weak:     { bg: "bg-red-50",      text: "text-red-700",     ring: "ring-red-200"     },
};

const SOURCE_LABELS: Record<string, string> = {
  airis:        "AIRIS",
  naukri_stub:  "Naukri",
  linkedin_stub:"LinkedIn",
};

// ── Component ─────────────────────────────────────────────────────────────────

interface CandidateCardProps {
  result: SourcingResult;
  sessionId: string;
  onActionUpdate?: (updated: SourcingResult) => void;
}

export function CandidateCard({ result, sessionId, onActionUpdate }: CandidateCardProps) {
  const [localResult, setLocalResult] = useState<SourcingResult>(result);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const name = [localResult.first_name, localResult.last_name].filter(Boolean).join(" ") || "Unknown";
  const initials = name.split(" ").map((n) => n[0]?.toUpperCase() ?? "?").slice(0, 2).join("");
  const tier = localResult.ats_tier;
  const tierStyle = tier ? TIER_STYLES[tier] ?? TIER_STYLES.Weak : null;
  const sourceLabel = SOURCE_LABELS[localResult.source] ?? localResult.source;
  const topSkills = (localResult.matched_skills?.length ? localResult.matched_skills : localResult.skills ?? []).slice(0, 3);
  const atsPercent = localResult.ats_score != null ? Math.round(localResult.ats_score) : null;

  async function handleAction(action: "shortlisted" | "rejected" | "imported") {
    if (busy) return;
    setBusy(true);
    setError(null);
    // Optimistic update
    setLocalResult((prev) => ({ ...prev, action }));
    try {
      const updated = await updateResultAction(sessionId, localResult.id, { action });
      setLocalResult(updated);
      onActionUpdate?.(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
      // Revert optimistic
      setLocalResult(result);
    } finally {
      setBusy(false);
    }
  }

  const isActed = localResult.action !== "pending";

  return (
    <div className={`rounded-xl border bg-white shadow-sm p-4 flex flex-col gap-3 transition-opacity ${isActed ? "opacity-80" : ""}`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 h-10 w-10 rounded-full bg-[#FF5A1F]/10 flex items-center justify-center text-[#FF5A1F] font-semibold text-sm">
          {initials}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-900 text-sm truncate">{name}</span>

            {/* Duplicate badge */}
            {localResult.is_duplicate && (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200">
                <AlertCircle className="h-3 w-3" /> Duplicate
              </span>
            )}

            {/* Source badge */}
            <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 ring-1 ring-slate-200">
              {sourceLabel}
            </span>
          </div>

          {/* Title / Location */}
          <div className="flex flex-wrap gap-x-3 text-xs text-gray-500 mt-0.5">
            {localResult.title && (
              <span className="flex items-center gap-1"><Briefcase className="h-3 w-3" />{localResult.title}</span>
            )}
            {localResult.location && (
              <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{localResult.location}</span>
            )}
          </div>
        </div>

        {/* Tier badge */}
        {tier && tierStyle && (
          <span className={`flex-shrink-0 text-xs font-semibold px-2 py-1 rounded-lg ring-1 ${tierStyle.bg} ${tierStyle.text} ${tierStyle.ring}`}>
            {tier}
          </span>
        )}
      </div>

      {/* ATS score bar */}
      {atsPercent != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Match score</span>
            <span className="font-medium text-gray-700">{atsPercent}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className={`h-full rounded-full ${atsPercent >= 85 ? "bg-emerald-500" : atsPercent >= 70 ? "bg-blue-500" : atsPercent >= 50 ? "bg-amber-500" : "bg-red-400"}`}
              style={{ width: `${atsPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Skills */}
      {topSkills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {topSkills.map((skill) => (
            <span key={skill} className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
              {skill}
            </span>
          ))}
        </div>
      )}

      {/* Recruiter summary */}
      {localResult.recruiter_summary && (
        <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">{localResult.recruiter_summary}</p>
      )}

      {/* Action area */}
      {error && <p className="text-xs text-red-600">{error}</p>}

      {localResult.action === "pending" ? (
        <div className="flex gap-2 pt-1">
          <button
            disabled={busy}
            onClick={() => void handleAction("shortlisted")}
            className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
          >
            <UserCheck className="h-3.5 w-3.5" /> Shortlist
          </button>
          <button
            disabled={busy}
            onClick={() => void handleAction("imported")}
            className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg border border-blue-300 text-blue-700 hover:bg-blue-50 disabled:opacity-50 transition-colors"
          >
            <Star className="h-3.5 w-3.5" /> Import
          </button>
          <button
            disabled={busy}
            onClick={() => void handleAction("rejected")}
            className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
          >
            <UserX className="h-3.5 w-3.5" /> Reject
          </button>
        </div>
      ) : (
        <div className="text-xs text-center font-medium capitalize text-gray-500 pt-1">
          {localResult.action === "shortlisted" && "✓ Shortlisted"}
          {localResult.action === "rejected" && "✗ Rejected"}
          {localResult.action === "imported" && "↓ Imported"}
        </div>
      )}
    </div>
  );
}
