from __future__ import annotations

"""
PIPE-008: Offer Management Service

Manages the full offer lifecycle:
  - Offer creation (salary, date, expiry, currency)
  - Candidate response (accepted → auto-placed, declined → rejected/revert, negotiating)
  - Offer revision during negotiation
  - Expiry alert tracking
  - Offer event audit log

Reuses:
  - PipelineService.transition_stage() for auto-placed / declined → rejected transitions
  - AccessScopeService for vendor/client scoping
  - _notify_* pattern for COMM-005 best-effort notifications
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.offer import PipelineOffer, PipelineOfferEvent
from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.offer import (
    OfferCreate,
    OfferEventType,
    OfferRespondRequest,
    OfferResponse,
    OfferRevise,
)
from app.schemas.pipeline import (
    PipelineStage,
    PipelineStageTransitionRequest,
)
from app.services.access_scope_service import AccessScopeService
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Number of days before expiry at which to fire the approaching-expiry alert.
EXPIRY_ALERT_DAYS_BEFORE = 3


class OfferService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)
        self._pipeline_svc = PipelineService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_pipeline(self, pipeline_id: UUID, organization_id: UUID, current_user: CurrentUser) -> Pipeline:
        """Fetch and scope-check the pipeline (raises 404 if inaccessible)."""
        return self._pipeline_svc.get_pipeline_by_id(pipeline_id, organization_id, current_user)

    def _get_offer(self, offer_id: UUID, pipeline_id: UUID, organization_id: UUID) -> PipelineOffer:
        """Fetch a specific offer by ID, scoped to org + pipeline."""
        offer = self.db.scalar(
            select(PipelineOffer).where(
                PipelineOffer.id == offer_id,
                PipelineOffer.pipeline_id == pipeline_id,
                PipelineOffer.organization_id == organization_id,
            )
        )
        if offer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found.")
        return offer

    def _get_active_offer(self, pipeline_id: UUID, organization_id: UUID) -> PipelineOffer | None:
        """Return the most-recent non-terminal offer for a pipeline (or None)."""
        return self.db.scalar(
            select(PipelineOffer)
            .where(
                PipelineOffer.pipeline_id == pipeline_id,
                PipelineOffer.organization_id == organization_id,
                PipelineOffer.offer_response.in_(
                    [OfferResponse.PENDING, OfferResponse.NEGOTIATING]
                ),
            )
            .order_by(PipelineOffer.created_at.desc())
            .limit(1)
        )

    @staticmethod
    def _enrich(offer: PipelineOffer) -> PipelineOffer:
        """Attach computed fields (days_until_expiry, is_expired) to the offer object.

        We attach them as transient attributes rather than DB columns so Pydantic's
        from_attributes=True picks them up during model_validate.
        """
        today = date.today()
        delta = (offer.expiry_date - today).days
        # Pydantic reads these as attributes on the ORM object.
        object.__setattr__(offer, "days_until_expiry", delta)
        object.__setattr__(offer, "is_expired", delta < 0)
        return offer

    def _record_event(
        self,
        *,
        offer: PipelineOffer,
        event_type: OfferEventType,
        actor_user_id: UUID | None,
        previous_response: str | None = None,
        new_response: str | None = None,
        notes: str | None = None,
    ) -> PipelineOfferEvent:
        event = PipelineOfferEvent(
            organization_id=offer.organization_id,
            pipeline_id=offer.pipeline_id,
            offer_id=offer.id,
            event_type=event_type.value,
            actor_user_id=actor_user_id,
            previous_response=previous_response,
            new_response=new_response,
            notes=notes,
        )
        self.db.add(event)
        return event

    # ── Public API ────────────────────────────────────────────────────────────

    def create_offer(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: OfferCreate,
    ) -> PipelineOffer:
        """
        Create a new offer for a pipeline that is currently in the 'offer' stage.

        Multiple offers may exist for the same pipeline (negotiation history),
        but only one can be active (pending/negotiating) at a time.
        """
        pipeline = self._get_pipeline(pipeline_id, organization_id, current_user)

        # Only create offers for pipelines that are at the offer stage.
        if pipeline.stage != PipelineStage.OFFER.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Offers can only be created when the pipeline is in the 'offer' stage. "
                    f"Current stage: '{pipeline.stage}'."
                ),
            )

        # Prevent duplicate active offers.
        existing_active = self._get_active_offer(pipeline_id, organization_id)
        if existing_active is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active offer already exists for this pipeline. "
                    "Respond to or revise the existing offer before creating a new one."
                ),
            )

        # Determine the previous stage (stage before offer — stored for potential revert on decline).
        # Look it up from stage history; fall back to "interview" as the standard predecessor.
        previous_stage = _get_stage_before_offer(self.db, pipeline_id, organization_id)

        actor_id: UUID | None = UUID(current_user.user_id) if current_user.user_id else None

        offer = PipelineOffer(
            organization_id=organization_id,
            pipeline_id=pipeline_id,
            candidate_id=pipeline.candidate_id,
            job_id=pipeline.job_id,
            offered_salary=payload.offered_salary,
            currency=payload.currency,
            offer_date=payload.offer_date,
            expiry_date=payload.expiry_date,
            offer_response=OfferResponse.PENDING.value,
            previous_stage=previous_stage,
            notes=payload.notes,
            created_by=actor_id,
            expiry_alert_sent=False,
        )
        self.db.add(offer)
        self.db.flush()  # Populate offer.id before creating the event.

        self._record_event(
            offer=offer,
            event_type=OfferEventType.OFFER_CREATED,
            actor_user_id=actor_id,
            new_response=OfferResponse.PENDING.value,
            notes=(
                f"Offer created: {payload.currency} {payload.offered_salary:,.2f} "
                f"· Valid until {payload.expiry_date.isoformat()}"
            ),
        )

        self.db.commit()
        self.db.refresh(offer)

        logger.info(
            "offer.created pipeline_id=%s offer_id=%s salary=%s %s actor=%s",
            pipeline_id, offer.id, payload.offered_salary, payload.currency, current_user.user_id,
        )

        try:
            _notify_offer_created(db=self.db, offer=offer, actor_user_id=actor_id)
        except Exception:
            logger.warning("offer.notify_created.failed offer_id=%s — suppressed", offer.id, exc_info=True)

        return self._enrich(offer)

    def get_offer(
        self,
        offer_id: UUID,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> PipelineOffer:
        self._get_pipeline(pipeline_id, organization_id, current_user)
        offer = self._get_offer(offer_id, pipeline_id, organization_id)
        return self._enrich(offer)

    def get_active_offer(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> PipelineOffer | None:
        self._get_pipeline(pipeline_id, organization_id, current_user)
        offer = self._get_active_offer(pipeline_id, organization_id)
        if offer is None:
            return None
        return self._enrich(offer)

    def list_offers(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[PipelineOffer]:
        """Return ALL offers for a pipeline (history), newest first."""
        self._get_pipeline(pipeline_id, organization_id, current_user)

        offers = list(
            self.db.scalars(
                select(PipelineOffer)
                .where(
                    PipelineOffer.pipeline_id == pipeline_id,
                    PipelineOffer.organization_id == organization_id,
                )
                .order_by(PipelineOffer.created_at.desc())
            ).all()
        )
        return [self._enrich(o) for o in offers]

    def revise_offer(
        self,
        offer_id: UUID,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: OfferRevise,
    ) -> PipelineOffer:
        """
        Update offer details while in 'pending' or 'negotiating' state.
        Each revision is recorded as an event (full negotiation history).
        """
        self._get_pipeline(pipeline_id, organization_id, current_user)
        offer = self._get_offer(offer_id, pipeline_id, organization_id)

        if offer.offer_response not in (OfferResponse.PENDING.value, OfferResponse.NEGOTIATING.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot revise an offer that has already been {offer.offer_response}. "
                    "Only pending or negotiating offers can be revised."
                ),
            )

        changes: list[str] = []
        if payload.offered_salary is not None and payload.offered_salary != offer.offered_salary:
            changes.append(f"salary {offer.currency} {offer.offered_salary:,.2f} → {payload.offered_salary:,.2f}")
            offer.offered_salary = payload.offered_salary
        if payload.currency is not None and payload.currency != offer.currency:
            changes.append(f"currency {offer.currency} → {payload.currency}")
            offer.currency = payload.currency
        if payload.expiry_date is not None and payload.expiry_date != offer.expiry_date:
            changes.append(f"expiry {offer.expiry_date.isoformat()} → {payload.expiry_date.isoformat()}")
            offer.expiry_date = payload.expiry_date
            offer.expiry_alert_sent = False  # Reset alert so it fires again for the new date.
        if payload.notes is not None:
            offer.notes = payload.notes

        if not changes:
            # Nothing changed — return early without touching DB.
            return self._enrich(offer)

        # Mark as negotiating after first revision (if still pending).
        if offer.offer_response == OfferResponse.PENDING.value:
            old_response = offer.offer_response
            offer.offer_response = OfferResponse.NEGOTIATING.value
        else:
            old_response = offer.offer_response

        actor_id: UUID | None = UUID(current_user.user_id) if current_user.user_id else None

        self.db.add(offer)
        self._record_event(
            offer=offer,
            event_type=OfferEventType.OFFER_REVISED,
            actor_user_id=actor_id,
            previous_response=old_response,
            new_response=offer.offer_response,
            notes="Revised: " + "; ".join(changes),
        )

        self.db.commit()
        self.db.refresh(offer)

        logger.info(
            "offer.revised offer_id=%s pipeline_id=%s changes=%s actor=%s",
            offer_id, pipeline_id, changes, current_user.user_id,
        )
        return self._enrich(offer)

    def respond_to_offer(
        self,
        offer_id: UUID,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: OfferRespondRequest,
    ) -> PipelineOffer:
        """
        Record the candidate's response and trigger the appropriate pipeline transition.

        accepted  → auto-transition pipeline: offer → placed
        declined  → record decline reason; transition: offer → rejected (or previous stage if flag set)
        negotiating → stay in offer stage; allow further revisions
        """
        pipeline = self._get_pipeline(pipeline_id, organization_id, current_user)
        offer = self._get_offer(offer_id, pipeline_id, organization_id)

        if offer.offer_response in (OfferResponse.ACCEPTED.value, OfferResponse.DECLINED.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This offer has already been {offer.offer_response}.",
            )

        # Pydantic validated that decline_reason is present when declining.
        previous_response = offer.offer_response
        new_response = payload.response.value
        actor_id: UUID | None = UUID(current_user.user_id) if current_user.user_id else None

        offer.offer_response = new_response
        if payload.response == OfferResponse.DECLINED:
            offer.decline_reason = payload.decline_reason

        self.db.add(offer)
        self._record_event(
            offer=offer,
            event_type=OfferEventType.RESPONSE_UPDATED,
            actor_user_id=actor_id,
            previous_response=previous_response,
            new_response=new_response,
            notes=payload.decline_reason if payload.response == OfferResponse.DECLINED else None,
        )

        self.db.commit()
        self.db.refresh(offer)

        logger.info(
            "offer.response offer_id=%s pipeline_id=%s response=%s actor=%s",
            offer_id, pipeline_id, new_response, current_user.user_id,
        )

        # ── Auto-transition pipeline stage ──────────────────────────────────
        if payload.response == OfferResponse.ACCEPTED:
            self._auto_transition(
                pipeline=pipeline,
                organization_id=organization_id,
                current_user=current_user,
                new_stage=PipelineStage.PLACED,
                reason="Offer accepted.",
            )
        elif payload.response == OfferResponse.DECLINED:
            if payload.revert_to_previous_stage and offer.previous_stage:
                target_stage = PipelineStage(offer.previous_stage)
                reason = f"Offer declined: {payload.decline_reason}"
            else:
                target_stage = PipelineStage.REJECTED
                reason = f"Offer declined: {payload.decline_reason}"
            self._auto_transition(
                pipeline=pipeline,
                organization_id=organization_id,
                current_user=current_user,
                new_stage=target_stage,
                reason=reason,
            )

        # ── Best-effort notification ─────────────────────────────────────────
        try:
            _notify_offer_response(db=self.db, offer=offer, response=new_response, actor_user_id=actor_id)
        except Exception:
            logger.warning("offer.notify_response.failed offer_id=%s — suppressed", offer_id, exc_info=True)

        return self._enrich(offer)

    def _auto_transition(
        self,
        *,
        pipeline: Pipeline,
        organization_id: UUID,
        current_user: CurrentUser,
        new_stage: PipelineStage,
        reason: str,
    ) -> None:
        """
        Fire a pipeline stage transition as a consequence of an offer response.
        Uses the existing PipelineService.transition_stage() so that all
        audit logs, notifications, and validation are preserved.
        """
        req = PipelineStageTransitionRequest(stage=new_stage, reason=reason)
        try:
            self._pipeline_svc.transition_stage(
                pipeline_id=pipeline.id,
                organization_id=organization_id,
                current_user=current_user,
                payload=req,
            )
        except Exception as exc:
            logger.error(
                "offer.auto_transition.failed pipeline_id=%s stage=%s error=%s",
                pipeline.id, new_stage, exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to auto-transition pipeline to '{new_stage}': {exc}",
            ) from exc

    def get_offer_events(
        self,
        offer_id: UUID,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[PipelineOfferEvent]:
        """Return the full ordered event history for an offer."""
        self._get_pipeline(pipeline_id, organization_id, current_user)
        self._get_offer(offer_id, pipeline_id, organization_id)

        return list(
            self.db.scalars(
                select(PipelineOfferEvent)
                .where(
                    PipelineOfferEvent.offer_id == offer_id,
                    PipelineOfferEvent.organization_id == organization_id,
                )
                .order_by(PipelineOfferEvent.created_at)
            ).all()
        )

    def get_pipeline_offer_history(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[PipelineOfferEvent]:
        """Return ALL offer events for a pipeline (across all offers) ordered chronologically."""
        self._get_pipeline(pipeline_id, organization_id, current_user)

        return list(
            self.db.scalars(
                select(PipelineOfferEvent)
                .where(
                    PipelineOfferEvent.pipeline_id == pipeline_id,
                    PipelineOfferEvent.organization_id == organization_id,
                )
                .order_by(PipelineOfferEvent.created_at)
            ).all()
        )

    # ── Expiry alert processing ────────────────────────────────────────────────

    def process_expiry_alerts(self) -> int:
        """
        Scan for offers approaching or past expiry and emit alerts.

        Returns the number of alerts sent.
        Intended to be called by the background scheduler.

        Alert conditions (either fires the notification):
          1. expiry_date is today or earlier (day-of / expired alert)
          2. expiry_date is within EXPIRY_ALERT_DAYS_BEFORE days
        """
        today = date.today()
        alert_threshold = today  # changed_at <= today + N days

        from datetime import timedelta
        threshold_date = today + timedelta(days=EXPIRY_ALERT_DAYS_BEFORE)

        # Offers that are still open AND haven't had an alert sent AND
        # are expiring within the threshold window.
        candidates = list(
            self.db.scalars(
                select(PipelineOffer)
                .where(
                    PipelineOffer.offer_response.in_(
                        [OfferResponse.PENDING.value, OfferResponse.NEGOTIATING.value]
                    ),
                    PipelineOffer.expiry_date <= threshold_date,
                    PipelineOffer.expiry_alert_sent.is_(False),
                )
            ).all()
        )

        count = 0
        for offer in candidates:
            try:
                days_left = (offer.expiry_date - today).days
                alert_msg = (
                    f"Offer expires today ({offer.expiry_date.isoformat()})!"
                    if days_left <= 0
                    else f"Offer expires in {days_left} day(s) on {offer.expiry_date.isoformat()}."
                )

                # Record the alert event.
                event = PipelineOfferEvent(
                    organization_id=offer.organization_id,
                    pipeline_id=offer.pipeline_id,
                    offer_id=offer.id,
                    event_type=OfferEventType.EXPIRY_ALERT_SENT.value,
                    actor_user_id=None,
                    notes=alert_msg,
                )
                self.db.add(event)
                offer.expiry_alert_sent = True
                self.db.add(offer)
                self.db.commit()

                count += 1
                logger.info(
                    "offer.expiry_alert offer_id=%s pipeline_id=%s days_left=%d",
                    offer.id, offer.pipeline_id, days_left,
                )

                # Best-effort COMM-005 notification.
                try:
                    _notify_expiry_alert(db=self.db, offer=offer, days_left=days_left)
                except Exception:
                    logger.warning(
                        "offer.notify_expiry.failed offer_id=%s — suppressed", offer.id, exc_info=True
                    )

            except Exception:
                self.db.rollback()
                logger.exception("offer.expiry_check.single_failed offer_id=%s — skipped", offer.id)

        return count


# ── Module-level helpers ───────────────────────────────────────────────────────

def _get_stage_before_offer(db: Session, pipeline_id: UUID, organization_id: UUID) -> str:
    """
    Look up the stage that immediately preceded the 'offer' stage in the pipeline's
    stage history.  Falls back to 'interview' (the canonical predecessor) if history
    is not available.
    """
    from app.models.pipeline import PipelineStageHistory  # local import to avoid circulars
    row = db.scalar(
        select(PipelineStageHistory.previous_stage)
        .where(
            PipelineStageHistory.pipeline_id == pipeline_id,
            PipelineStageHistory.organization_id == organization_id,
            PipelineStageHistory.new_stage == PipelineStage.OFFER.value,
        )
        .order_by(PipelineStageHistory.transitioned_at.desc())
        .limit(1)
    )
    return row or PipelineStage.INTERVIEW.value


# ── COMM-005 notification stubs ───────────────────────────────────────────────

def _notify_offer_created(*, db: Session, offer: PipelineOffer, actor_user_id: UUID | None) -> None:
    """Record a CandidateInteraction when an offer is created (COMM-005)."""
    try:
        from app.candidate_management.models import CandidateInteraction, InteractionType
        from app.candidate_management.models import Candidate as CMCandidate
        from sqlalchemy import select as _sel

        cm = db.scalar(_sel(CMCandidate).where(CMCandidate.id == offer.candidate_id))
        if cm is None:
            return
        interaction = CandidateInteraction(
            org_id=cm.org_id,
            workspace_id=cm.workspace_id,
            candidate_id=cm.id,
            interaction_type=InteractionType.STAGE_CHANGE,
            title="Offer created",
            body=(
                f"Offer of {offer.currency} {offer.offered_salary:,.2f} extended. "
                f"Expires: {offer.expiry_date.isoformat()}."
            ),
            actor_user_id=actor_user_id,
        )
        db.add(interaction)
        db.commit()
    except Exception:
        logger.warning("offer.notify_created.comm005.failed offer_id=%s — suppressed", offer.id, exc_info=True)


def _notify_offer_response(
    *, db: Session, offer: PipelineOffer, response: str, actor_user_id: UUID | None
) -> None:
    try:
        from app.candidate_management.models import CandidateInteraction, InteractionType
        from app.candidate_management.models import Candidate as CMCandidate
        from sqlalchemy import select as _sel

        cm = db.scalar(_sel(CMCandidate).where(CMCandidate.id == offer.candidate_id))
        if cm is None:
            return
        interaction = CandidateInteraction(
            org_id=cm.org_id,
            workspace_id=cm.workspace_id,
            candidate_id=cm.id,
            interaction_type=InteractionType.STAGE_CHANGE,
            title=f"Offer response: {response}",
            body=(
                f"Candidate responded to offer with: {response}."
                + (f"\nReason: {offer.decline_reason}" if offer.decline_reason else "")
            ),
            actor_user_id=actor_user_id,
        )
        db.add(interaction)
        db.commit()
    except Exception:
        logger.warning("offer.notify_response.comm005.failed offer_id=%s — suppressed", offer.id, exc_info=True)


def _notify_expiry_alert(*, db: Session, offer: PipelineOffer, days_left: int) -> None:
    try:
        from app.candidate_management.models import CandidateInteraction, InteractionType
        from app.candidate_management.models import Candidate as CMCandidate
        from sqlalchemy import select as _sel

        cm = db.scalar(_sel(CMCandidate).where(CMCandidate.id == offer.candidate_id))
        if cm is None:
            return
        msg = (
            f"Offer expiring today ({offer.expiry_date.isoformat()})!"
            if days_left <= 0
            else f"Offer expires in {days_left} day(s) ({offer.expiry_date.isoformat()})."
        )
        interaction = CandidateInteraction(
            org_id=cm.org_id,
            workspace_id=cm.workspace_id,
            candidate_id=cm.id,
            interaction_type=InteractionType.STAGE_CHANGE,
            title="Offer expiry alert",
            body=msg,
            actor_user_id=None,
        )
        db.add(interaction)
        db.commit()
    except Exception:
        logger.warning("offer.notify_expiry.comm005.failed offer_id=%s — suppressed", offer.id, exc_info=True)
