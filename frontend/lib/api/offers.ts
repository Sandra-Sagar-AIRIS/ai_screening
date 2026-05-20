/**
 * PIPE-008: Offer Management API helpers.
 *
 * Endpoints live under /api/v1/pipelines/{pipelineId}/offers
 */
import { apiRequest, invalidateApiCache } from "@/lib/api/client";
import type {
  OfferCreatePayload,
  OfferRespondPayload,
  OfferRevisePayload,
  PipelineOffer,
  PipelineOfferEvent,
} from "@/lib/api/types";

function offerBase(pipelineId: string): string {
  return `/pipelines/${pipelineId}/offers`;
}

/** Create a new offer for a pipeline that is in the 'offer' stage. */
export async function createOffer(
  pipelineId: string,
  payload: OfferCreatePayload
): Promise<PipelineOffer> {
  const result = await apiRequest<PipelineOffer>(offerBase(pipelineId), {
    method: "POST",
    body: JSON.stringify(payload),
  }, 0);
  invalidateApiCache(`/pipelines/${pipelineId}`);
  return result;
}

/** List all offers (history) for a pipeline, newest first. */
export async function listOffers(pipelineId: string): Promise<PipelineOffer[]> {
  return apiRequest<PipelineOffer[]>(offerBase(pipelineId), {}, 0);
}

/** Get the current active (pending/negotiating) offer, or null. */
export async function getActiveOffer(pipelineId: string): Promise<PipelineOffer | null> {
  return apiRequest<PipelineOffer | null>(`${offerBase(pipelineId)}/active`, {}, 0);
}

/** Get a specific offer by ID. */
export async function getOffer(pipelineId: string, offerId: string): Promise<PipelineOffer> {
  return apiRequest<PipelineOffer>(`${offerBase(pipelineId)}/${offerId}`, {}, 0);
}

/** Revise salary, currency, or expiry_date while the offer is still open. */
export async function reviseOffer(
  pipelineId: string,
  offerId: string,
  payload: OfferRevisePayload
): Promise<PipelineOffer> {
  const result = await apiRequest<PipelineOffer>(`${offerBase(pipelineId)}/${offerId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, 0);
  invalidateApiCache(`/pipelines/${pipelineId}`);
  return result;
}

/** Submit candidate response (accepted / declined / negotiating). */
export async function respondToOffer(
  pipelineId: string,
  offerId: string,
  payload: OfferRespondPayload
): Promise<PipelineOffer> {
  const result = await apiRequest<PipelineOffer>(`${offerBase(pipelineId)}/${offerId}/respond`, {
    method: "POST",
    body: JSON.stringify(payload),
  }, 0);
  // Accepting auto-transitions pipeline — invalidate pipeline cache too.
  invalidateApiCache(`/pipelines/${pipelineId}`);
  invalidateApiCache("/pipelines");
  return result;
}

/** Get the full event history for a specific offer. */
export async function getOfferHistory(
  pipelineId: string,
  offerId: string
): Promise<PipelineOfferEvent[]> {
  return apiRequest<PipelineOfferEvent[]>(`${offerBase(pipelineId)}/${offerId}/history`, {}, 0);
}

/** Get all offer events for a pipeline (across all offers), chronological. */
export async function getPipelineOfferHistory(
  pipelineId: string
): Promise<PipelineOfferEvent[]> {
  return apiRequest<PipelineOfferEvent[]>(`${offerBase(pipelineId)}/history/all`, {}, 0);
}
