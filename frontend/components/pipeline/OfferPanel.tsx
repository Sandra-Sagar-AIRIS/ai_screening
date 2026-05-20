"use client";

/**
 * PIPE-008: Offer Panel
 *
 * Main offer management panel shown on the pipeline detail page when the
 * pipeline is in the 'offer' stage.
 *
 * States:
 *   - No offer: show OfferForm (create)
 *   - Pending/Negotiating: show OfferDetails + OfferResponsePanel + OfferExpiryAlert
 *   - Accepted/Declined: show read-only summary
 */

import { useCallback, useEffect, useState } from "react";
import {
  DollarSign,
  Calendar,
  Clock,
  Loader2,
  RefreshCw,
  CheckCircle2,
  XCircle,
  MessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import {
  createOffer,
  getActiveOffer,
  respondToOffer,
  reviseOffer,
} from "@/lib/api/offers";
import type {
  OfferCreatePayload,
  OfferRespondPayload,
  PipelineOffer,
} from "@/lib/api/types";
import { OfferExpiryAlert } from "./OfferExpiryAlert";
import { DeclineReasonModal } from "./DeclineReasonModal";

// ── Currency options ──────────────────────────────────────────────────────────
const CURRENCIES = ["USD", "GBP", "EUR", "AUD", "CAD", "INR", "SGD", "AED"];

// ── Response badge ────────────────────────────────────────────────────────────
function ResponseBadge({ response }: { response: string }) {
  const map: Record<string, string> = {
    pending:     "bg-amber-50 text-amber-700 border-amber-200",
    negotiating: "bg-sky-50 text-sky-700 border-sky-200",
    accepted:    "bg-emerald-50 text-emerald-700 border-emerald-200",
    declined:    "bg-red-50 text-red-700 border-red-200",
  };
  const labels: Record<string, string> = {
    pending:     "Pending",
    negotiating: "Negotiating",
    accepted:    "Accepted",
    declined:    "Declined",
  };
  const cls = map[response] ?? "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {labels[response] ?? response}
    </span>
  );
}

// ── Offer Create Form ─────────────────────────────────────────────────────────
function OfferCreateForm({
  pipelineId,
  onCreated,
}: {
  pipelineId: string;
  onCreated: (offer: PipelineOffer) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [salary, setSalary] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [offerDate, setOfferDate] = useState(today);
  const [expiryDate, setExpiryDate] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    !!salary && parseFloat(salary) > 0 &&
    !!offerDate && !!expiryDate &&
    expiryDate >= offerDate &&
    !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload: OfferCreatePayload = {
        offered_salary: parseFloat(salary),
        currency,
        offer_date: offerDate,
        expiry_date: expiryDate,
        notes: notes.trim() || undefined,
      };
      const offer = await createOffer(pipelineId, payload);
      onCreated(offer);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create offer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {/* Salary */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
            Offered Salary <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            min="1"
            step="0.01"
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
            placeholder="e.g. 85000"
            disabled={submitting}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
          />
        </div>

        {/* Currency */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
            Currency <span className="text-red-400">*</span>
          </label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            disabled={submitting}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Offer Date */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
            Offer Date <span className="text-red-400">*</span>
          </label>
          <input
            type="date"
            value={offerDate}
            onChange={(e) => setOfferDate(e.target.value)}
            disabled={submitting}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
          />
        </div>

        {/* Expiry Date */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
            Expiry Date <span className="text-red-400">*</span>
          </label>
          <input
            type="date"
            value={expiryDate}
            min={offerDate}
            onChange={(e) => setExpiryDate(e.target.value)}
            disabled={submitting}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50"
          />
          {expiryDate && offerDate && expiryDate < offerDate && (
            <p className="mt-1 text-xs text-red-500">Expiry must be on or after offer date.</p>
          )}
        </div>
      </div>

      {/* Notes */}
      <div>
        <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">
          Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="Internal notes about this offer…"
          disabled={submitting}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-1 focus:ring-orange-400 disabled:opacity-50 resize-none"
        />
      </div>

      {error && (
        <p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      <div className="flex justify-end">
        <Button
          type="submit"
          disabled={!canSubmit}
          className="bg-[#FF5A1F] hover:bg-orange-600 text-white disabled:opacity-50"
        >
          {submitting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Creating…
            </>
          ) : (
            "Create Offer"
          )}
        </Button>
      </div>
    </form>
  );
}

// ── Offer Detail View ─────────────────────────────────────────────────────────
function OfferDetailView({
  offer,
  pipelineId,
  candidateName,
  onUpdated,
}: {
  offer: PipelineOffer;
  pipelineId: string;
  candidateName?: string;
  onUpdated: (offer: PipelineOffer) => void;
}) {
  const [showDeclineModal, setShowDeclineModal] = useState(false);
  const [responding, setResponding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOpen = offer.offer_response === "pending" || offer.offer_response === "negotiating";

  async function handleResponse(payload: OfferRespondPayload) {
    setResponding(true);
    setError(null);
    try {
      const updated = await respondToOffer(pipelineId, offer.id, payload);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit response.");
    } finally {
      setResponding(false);
      setShowDeclineModal(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Expiry alert */}
      <OfferExpiryAlert offer={offer} />

      {/* Offer summary card */}
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Current Offer</h3>
          <ResponseBadge response={offer.offer_response} />
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Salary</p>
            <p className="mt-0.5 font-bold text-slate-900 text-base">
              {offer.currency}{" "}
              {parseFloat(offer.offered_salary).toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Currency</p>
            <p className="mt-0.5 text-slate-700">{offer.currency}</p>
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Offer Date</p>
            <p className="mt-0.5 text-slate-700">
              {new Date(offer.offer_date).toLocaleDateString()}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Expires</p>
            <p className={`mt-0.5 font-medium ${offer.is_expired ? "text-red-600" : "text-slate-700"}`}>
              {new Date(offer.expiry_date).toLocaleDateString()}
              {offer.days_until_expiry !== null && !offer.is_expired && offer.days_until_expiry <= 3 && (
                <span className="ml-1 text-amber-500 text-xs">({offer.days_until_expiry}d left)</span>
              )}
            </p>
          </div>
        </div>

        {offer.notes && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Notes</p>
            <p className="mt-0.5 text-sm text-slate-600 italic">{offer.notes}</p>
          </div>
        )}

        {offer.decline_reason && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Decline Reason</p>
            <p className="mt-0.5 text-sm text-red-600">{offer.decline_reason}</p>
          </div>
        )}
      </div>

      {/* Response actions — only for open offers */}
      {isOpen && (
        <div className="space-y-2">
          {error && (
            <p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              type="button"
              onClick={() => void handleResponse({ response: "accepted" })}
              disabled={responding}
              className="bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
            >
              {responding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              <span className="ml-1.5">Accept Offer</span>
            </Button>
            <Button
              type="button"
              onClick={() => void handleResponse({ response: "negotiating" })}
              disabled={responding || offer.offer_response === "negotiating"}
              variant="outline"
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span className="ml-1.5">Mark as Negotiating</span>
            </Button>
            <Button
              type="button"
              onClick={() => setShowDeclineModal(true)}
              disabled={responding}
              variant="outline"
              className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
            >
              <XCircle className="h-3.5 w-3.5" />
              <span className="ml-1.5">Decline</span>
            </Button>
          </div>
        </div>
      )}

      {showDeclineModal && (
        <DeclineReasonModal
          candidateName={candidateName}
          previousStage={offer.previous_stage}
          submitting={responding}
          onConfirm={(result) =>
            void handleResponse({
              response: "declined",
              decline_reason: result.decline_reason,
              revert_to_previous_stage: result.revert_to_previous_stage,
            })
          }
          onCancel={() => setShowDeclineModal(false)}
        />
      )}
    </div>
  );
}

// ── Main OfferPanel ───────────────────────────────────────────────────────────

interface OfferPanelProps {
  pipelineId: string;
  pipelineStage: string;
  candidateName?: string;
}

export function OfferPanel({ pipelineId, pipelineStage, candidateName }: OfferPanelProps) {
  const [offer, setOffer] = useState<PipelineOffer | null | undefined>(undefined); // undefined = loading
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getActiveOffer(pipelineId)
      .then(setOffer)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load offer.");
        setOffer(null);
      });
  }, [pipelineId]);

  useEffect(() => {
    // Only load offer data when pipeline is at or past the offer stage.
    if (pipelineStage === "offer" || pipelineStage === "placed" || pipelineStage === "rejected") {
      load();
    }
  }, [pipelineId, pipelineStage, load]);

  // Not in offer stage — nothing to render.
  if (pipelineStage !== "offer") return null;

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm space-y-4">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50">
            <DollarSign className="h-4 w-4 text-amber-500" />
          </div>
          <h2 className="text-[15px] font-bold text-slate-800">Offer Details</h2>
        </div>
        {offer !== undefined && offer !== null && (
          <button
            type="button"
            onClick={load}
            className="text-slate-400 hover:text-orange-500 transition-colors"
            aria-label="Refresh offer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Loading */}
      {offer === undefined && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading offer details…
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      {/* No offer yet — show create form */}
      {offer === null && !error && (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            No offer has been created yet. Fill in the details below to extend an offer to this candidate.
          </p>
          <OfferCreateForm pipelineId={pipelineId} onCreated={setOffer} />
        </div>
      )}

      {/* Offer exists — show detail view */}
      {offer !== null && offer !== undefined && (
        <OfferDetailView
          offer={offer}
          pipelineId={pipelineId}
          candidateName={candidateName}
          onUpdated={setOffer}
        />
      )}
    </div>
  );
}
