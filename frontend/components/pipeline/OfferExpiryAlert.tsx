"use client";

/**
 * PIPE-008: Offer Expiry Alert Banner
 *
 * Displays a prominent warning when an offer is approaching or past its expiry date.
 */

import { AlertTriangle, Clock } from "lucide-react";
import type { PipelineOffer } from "@/lib/api/types";

interface OfferExpiryAlertProps {
  offer: PipelineOffer;
}

export function OfferExpiryAlert({ offer }: OfferExpiryAlertProps) {
  const { days_until_expiry, is_expired, offer_response } = offer;

  // Only show for open offers (pending/negotiating).
  if (offer_response === "accepted" || offer_response === "declined") return null;
  if (days_until_expiry === null) return null;

  // No alert needed if expiry is comfortably in the future.
  if (!is_expired && days_until_expiry > 3) return null;

  if (is_expired) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-red-700">Offer has expired</p>
          <p className="text-xs text-red-500 mt-0.5">
            This offer expired on {new Date(offer.expiry_date).toLocaleDateString()}.
            Please update or withdraw the offer.
          </p>
        </div>
      </div>
    );
  }

  const urgency = days_until_expiry === 0 ? "today" : `in ${days_until_expiry} day${days_until_expiry !== 1 ? "s" : ""}`;
  const isUrgent = days_until_expiry <= 1;

  return (
    <div
      className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${
        isUrgent
          ? "border-orange-200 bg-orange-50"
          : "border-amber-100 bg-amber-50"
      }`}
    >
      <Clock className={`h-4 w-4 mt-0.5 shrink-0 ${isUrgent ? "text-orange-500" : "text-amber-500"}`} />
      <div>
        <p className={`text-sm font-semibold ${isUrgent ? "text-orange-700" : "text-amber-700"}`}>
          Offer expires {urgency}
        </p>
        <p className={`text-xs mt-0.5 ${isUrgent ? "text-orange-500" : "text-amber-500"}`}>
          Candidate must respond by {new Date(offer.expiry_date).toLocaleDateString()}.
        </p>
      </div>
    </div>
  );
}
