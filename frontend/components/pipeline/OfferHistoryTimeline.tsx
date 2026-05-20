"use client";

/**
 * PIPE-008: Offer History Timeline
 *
 * Displays the full event audit log for all offers on a pipeline record.
 * Fetches from GET /pipelines/{id}/offers/history/all
 */

import { useEffect, useState } from "react";
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  DollarSign,
  XCircle,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { getPipelineOfferHistory } from "@/lib/api/offers";
import type { PipelineOfferEvent } from "@/lib/api/types";

const EVENT_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  offer_created:      { label: "Offer Created",       icon: DollarSign,    color: "text-emerald-500" },
  offer_revised:      { label: "Offer Revised",       icon: RefreshCw,     color: "text-sky-500"     },
  response_updated:   { label: "Response Updated",    icon: CheckCircle,   color: "text-orange-500"  },
  expiry_alert_sent:  { label: "Expiry Alert Sent",   icon: AlertTriangle, color: "text-amber-500"   },
  offer_expired:      { label: "Offer Expired",       icon: Clock,         color: "text-red-400"     },
};

const RESPONSE_LABELS: Record<string, string> = {
  pending: "Pending",
  accepted: "Accepted",
  declined: "Declined",
  negotiating: "Negotiating",
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

type Props = {
  pipelineId: string;
  defaultExpanded?: boolean;
};

export function OfferHistoryTimeline({ pipelineId, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [events, setEvents] = useState<PipelineOfferEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded) return;
    setLoading(true);
    setError(null);
    getPipelineOfferHistory(pipelineId)
      .then(setEvents)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load offer history.");
      })
      .finally(() => setLoading(false));
  }, [pipelineId, expanded]);

  return (
    <div className="rounded-xl border border-slate-100 bg-white shadow-sm">
      {/* Header / toggle */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
      >
        <span className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-slate-400" />
          Offer History
          {events.length > 0 && (
            <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
              {events.length}
            </span>
          )}
        </span>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-slate-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-400" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3">
          {loading && (
            <p className="text-xs text-slate-400 animate-pulse">Loading offer history…</p>
          )}
          {error && <p className="text-xs text-red-500">{error}</p>}
          {!loading && !error && events.length === 0 && (
            <p className="text-xs text-slate-400 italic">No offer activity recorded yet.</p>
          )}

          {!loading && !error && events.length > 0 && (
            <ol className="space-y-0">
              {events.map((evt, i) => {
                const meta = EVENT_META[evt.event_type] ?? {
                  label: evt.event_type,
                  icon: Clock,
                  color: "text-slate-400",
                };
                const Icon = meta.icon;
                const isLast = i === events.length - 1;

                return (
                  <li key={evt.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {/* Spine */}
                    {!isLast && (
                      <div className="absolute left-[9px] top-5 bottom-0 w-px bg-slate-200" />
                    )}

                    {/* Dot */}
                    <div className="mt-1 shrink-0">
                      <Icon className={`h-5 w-5 ${meta.color}`} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800">{meta.label}</p>

                      {evt.previous_response && evt.new_response && (
                        <p className="text-xs text-slate-500 mt-0.5">
                          {RESPONSE_LABELS[evt.previous_response] ?? evt.previous_response}
                          {" → "}
                          <span className={evt.new_response === "accepted"
                            ? "text-emerald-600 font-semibold"
                            : evt.new_response === "declined"
                            ? "text-red-600 font-semibold"
                            : "text-orange-600 font-semibold"
                          }>
                            {RESPONSE_LABELS[evt.new_response] ?? evt.new_response}
                          </span>
                        </p>
                      )}

                      {evt.notes && (
                        <p className="mt-1 text-xs text-slate-500 italic">
                          &ldquo;{evt.notes}&rdquo;
                        </p>
                      )}

                      <p className="mt-0.5 text-xs text-slate-400">{formatDate(evt.created_at)}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
