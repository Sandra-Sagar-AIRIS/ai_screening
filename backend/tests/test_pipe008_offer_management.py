"""
PIPE-008: Offer Management — Test Suite

Covers:
  - Schema validation (OfferCreate, OfferRespondRequest, OfferRevise)
  - Offer creation lifecycle
  - Candidate response flows (accepted, declined, negotiating)
  - Auto-transition on acceptance (offer → placed)
  - Decline flow (offer → rejected, or revert to previous stage)
  - Offer revision during negotiation
  - Expiry alert processing
  - Offer history persistence
  - Org scoping / access control
  - Duplicate active offer prevention
  - Pipeline stage guard (must be in 'offer' stage)
  - Invalid inputs
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.offer import (
    OfferCreate,
    OfferEventType,
    OfferRespondRequest,
    OfferResponse,
    OfferRevise,
)
from app.services.offer_service import OfferService, EXPIRY_ALERT_DAYS_BEFORE


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_user(org_id=None, user_id=None, role="recruiter"):
    u = MagicMock()
    u.organization_id = str(org_id or uuid4())
    u.user_id = str(user_id or uuid4())
    u.role = role
    return u


def _make_pipeline(stage="offer"):
    p = MagicMock()
    p.id = uuid4()
    p.stage = stage
    p.candidate_id = uuid4()
    p.job_id = uuid4()
    p.organization_id = uuid4()
    return p


def _make_offer(response="pending", expiry_days=10):
    o = MagicMock()
    o.id = uuid4()
    o.organization_id = uuid4()
    o.pipeline_id = uuid4()
    o.candidate_id = uuid4()
    o.job_id = uuid4()
    o.offered_salary = Decimal("75000.00")
    o.currency = "USD"
    o.offer_date = date.today()
    o.expiry_date = date.today() + timedelta(days=expiry_days)
    o.offer_response = response
    o.decline_reason = None
    o.previous_stage = "interview"
    o.expiry_alert_sent = False
    o.notes = None
    o.created_by = uuid4()
    return o


TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)
YESTERDAY = TODAY - timedelta(days=1)


# ── AIR-531: Schema / Validation Tests ───────────────────────────────────────

class TestOfferCreateSchema:
    def test_valid_offer(self):
        payload = OfferCreate(
            offered_salary=Decimal("85000"),
            currency="GBP",
            offer_date=TODAY,
            expiry_date=NEXT_WEEK,
        )
        assert payload.currency == "GBP"
        assert payload.offered_salary == Decimal("85000")

    def test_currency_normalized_to_upper(self):
        payload = OfferCreate(
            offered_salary=Decimal("50000"),
            currency="usd",
            offer_date=TODAY,
            expiry_date=TOMORROW,
        )
        assert payload.currency == "USD"

    def test_expiry_before_offer_date_rejected(self):
        with pytest.raises(ValidationError, match="expiry_date must be on or after offer_date"):
            OfferCreate(
                offered_salary=Decimal("60000"),
                currency="USD",
                offer_date=TOMORROW,
                expiry_date=TODAY,
            )

    def test_expiry_equal_to_offer_date_allowed(self):
        payload = OfferCreate(
            offered_salary=Decimal("60000"),
            currency="EUR",
            offer_date=TODAY,
            expiry_date=TODAY,
        )
        assert payload.expiry_date == TODAY

    def test_zero_salary_rejected(self):
        with pytest.raises(ValidationError):
            OfferCreate(
                offered_salary=Decimal("0"),
                currency="USD",
                offer_date=TODAY,
                expiry_date=NEXT_WEEK,
            )

    def test_negative_salary_rejected(self):
        with pytest.raises(ValidationError):
            OfferCreate(
                offered_salary=Decimal("-1000"),
                currency="USD",
                offer_date=TODAY,
                expiry_date=NEXT_WEEK,
            )

    def test_currency_too_long_rejected(self):
        with pytest.raises(ValidationError):
            OfferCreate(
                offered_salary=Decimal("50000"),
                currency="USDD",
                offer_date=TODAY,
                expiry_date=NEXT_WEEK,
            )

    def test_currency_too_short_rejected(self):
        with pytest.raises(ValidationError):
            OfferCreate(
                offered_salary=Decimal("50000"),
                currency="US",
                offer_date=TODAY,
                expiry_date=NEXT_WEEK,
            )


class TestOfferRespondSchema:
    def test_accepted_no_reason_required(self):
        req = OfferRespondRequest(response=OfferResponse.ACCEPTED)
        assert req.response == OfferResponse.ACCEPTED

    def test_negotiating_no_reason_required(self):
        req = OfferRespondRequest(response=OfferResponse.NEGOTIATING)
        assert req.response == OfferResponse.NEGOTIATING

    def test_declined_requires_reason(self):
        with pytest.raises(ValidationError, match="decline reason"):
            OfferRespondRequest(response=OfferResponse.DECLINED)

    def test_declined_with_short_reason_rejected(self):
        with pytest.raises(ValidationError, match="decline reason"):
            OfferRespondRequest(response=OfferResponse.DECLINED, decline_reason="too short")

    def test_declined_with_sufficient_reason(self):
        req = OfferRespondRequest(
            response=OfferResponse.DECLINED,
            decline_reason="Salary below market rate for this role.",
        )
        assert req.decline_reason is not None

    def test_revert_to_previous_stage_default_false(self):
        req = OfferRespondRequest(response=OfferResponse.ACCEPTED)
        assert req.revert_to_previous_stage is False


# ── AIR-531: Offer Creation Tests ─────────────────────────────────────────────

class TestOfferCreation:
    def _make_service(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db
        svc._scope = MagicMock()
        svc._pipeline_svc = MagicMock()
        return svc, db

    def test_create_offer_rejects_non_offer_stage(self):
        svc, _ = self._make_service()
        pipeline = _make_pipeline(stage="interview")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_active_offer = MagicMock(return_value=None)

        user = _make_user(org_id=pipeline.organization_id)
        payload = OfferCreate(
            offered_salary=Decimal("80000"),
            currency="USD",
            offer_date=TODAY,
            expiry_date=NEXT_WEEK,
        )

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.create_offer(pipeline.id, pipeline.organization_id, user, payload)
        assert exc_info.value.status_code == 422
        assert "'offer' stage" in exc_info.value.detail.lower()

    def test_create_offer_rejects_duplicate_active(self):
        svc, _ = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        active_offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_active_offer = MagicMock(return_value=active_offer)

        user = _make_user()
        payload = OfferCreate(
            offered_salary=Decimal("80000"),
            currency="USD",
            offer_date=TODAY,
            expiry_date=NEXT_WEEK,
        )

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.create_offer(pipeline.id, pipeline.organization_id, user, payload)
        assert exc_info.value.status_code == 409

    def test_create_offer_succeeds_for_offer_stage(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_active_offer = MagicMock(return_value=None)

        created_offer = _make_offer(response="pending")
        db.add = MagicMock()
        db.flush = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.scalar = MagicMock(return_value=None)  # no previous stage history

        with patch("app.services.offer_service.PipelineOffer", return_value=created_offer):
            with patch("app.services.offer_service._notify_offer_created"):
                with patch.object(svc, "_record_event"):
                    with patch.object(svc, "_enrich", side_effect=lambda o: o):
                        result = svc.create_offer(
                            pipeline_id=pipeline.id,
                            organization_id=pipeline.organization_id,
                            current_user=_make_user(),
                            payload=OfferCreate(
                                offered_salary=Decimal("90000"),
                                currency="USD",
                                offer_date=TODAY,
                                expiry_date=NEXT_WEEK,
                            ),
                        )
        assert result is created_offer


# ── AIR-532: Candidate Response Tests ────────────────────────────────────────

class TestOfferResponse:
    def _make_service(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db
        svc._scope = MagicMock()
        svc._pipeline_svc = MagicMock()
        return svc, db

    def test_respond_to_already_accepted_raises_conflict(self):
        svc, _ = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="accepted")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.respond_to_offer(
                offer.id, pipeline.id, pipeline.organization_id,
                _make_user(), OfferRespondRequest(response=OfferResponse.ACCEPTED),
            )
        assert exc_info.value.status_code == 409

    def test_accepted_triggers_placed_transition(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        auto_transition_calls = []

        def fake_auto_transition(*, pipeline, organization_id, current_user, new_stage, reason):
            auto_transition_calls.append(new_stage)

        svc._auto_transition = fake_auto_transition

        with patch("app.services.offer_service._notify_offer_response"):
            with patch.object(svc, "_record_event"):
                with patch.object(svc, "_enrich", side_effect=lambda o: o):
                    svc.respond_to_offer(
                        offer.id, pipeline.id, pipeline.organization_id,
                        _make_user(),
                        OfferRespondRequest(response=OfferResponse.ACCEPTED),
                    )

        from app.schemas.pipeline import PipelineStage
        assert len(auto_transition_calls) == 1
        assert auto_transition_calls[0] == PipelineStage.PLACED

    def test_declined_triggers_rejected_transition(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        transition_calls = []

        def fake_auto_transition(*, pipeline, organization_id, current_user, new_stage, reason):
            transition_calls.append((new_stage, reason))

        svc._auto_transition = fake_auto_transition

        decline_reason = "Compensation does not meet expectations for this role."
        with patch("app.services.offer_service._notify_offer_response"):
            with patch.object(svc, "_record_event"):
                with patch.object(svc, "_enrich", side_effect=lambda o: o):
                    svc.respond_to_offer(
                        offer.id, pipeline.id, pipeline.organization_id,
                        _make_user(),
                        OfferRespondRequest(
                            response=OfferResponse.DECLINED,
                            decline_reason=decline_reason,
                        ),
                    )

        from app.schemas.pipeline import PipelineStage
        assert len(transition_calls) == 1
        new_stage, reason = transition_calls[0]
        assert new_stage == PipelineStage.REJECTED
        assert decline_reason in reason

    def test_declined_with_revert_triggers_previous_stage_transition(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="pending")
        offer.previous_stage = "interview"
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        transition_calls = []

        def fake_auto_transition(*, pipeline, organization_id, current_user, new_stage, reason):
            transition_calls.append(new_stage)

        svc._auto_transition = fake_auto_transition

        with patch("app.services.offer_service._notify_offer_response"):
            with patch.object(svc, "_record_event"):
                with patch.object(svc, "_enrich", side_effect=lambda o: o):
                    svc.respond_to_offer(
                        offer.id, pipeline.id, pipeline.organization_id,
                        _make_user(),
                        OfferRespondRequest(
                            response=OfferResponse.DECLINED,
                            decline_reason="Compensation does not meet expectations.",
                            revert_to_previous_stage=True,
                        ),
                    )

        from app.schemas.pipeline import PipelineStage
        assert transition_calls[0] == PipelineStage.INTERVIEW

    def test_negotiating_does_not_trigger_transition(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        transition_calls = []
        svc._auto_transition = lambda **kw: transition_calls.append(kw)

        with patch("app.services.offer_service._notify_offer_response"):
            with patch.object(svc, "_record_event"):
                with patch.object(svc, "_enrich", side_effect=lambda o: o):
                    svc.respond_to_offer(
                        offer.id, pipeline.id, pipeline.organization_id,
                        _make_user(),
                        OfferRespondRequest(response=OfferResponse.NEGOTIATING),
                    )

        assert len(transition_calls) == 0

    def test_decline_reason_stored_on_offer(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        svc._auto_transition = MagicMock()

        decline_reason = "The offered package is significantly below our expectations."
        with patch("app.services.offer_service._notify_offer_response"):
            with patch.object(svc, "_record_event"):
                with patch.object(svc, "_enrich", side_effect=lambda o: o):
                    svc.respond_to_offer(
                        offer.id, pipeline.id, pipeline.organization_id,
                        _make_user(),
                        OfferRespondRequest(
                            response=OfferResponse.DECLINED,
                            decline_reason=decline_reason,
                        ),
                    )

        assert offer.decline_reason == decline_reason


# ── AIR-531: Offer Revision Tests ─────────────────────────────────────────────

class TestOfferRevision:
    def _make_service(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db
        svc._scope = MagicMock()
        svc._pipeline_svc = MagicMock()
        return svc, db

    def test_revise_accepted_offer_rejected(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline(stage="offer")
        offer = _make_offer(response="accepted")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.revise_offer(
                offer.id, pipeline.id, pipeline.organization_id,
                _make_user(), OfferRevise(offered_salary=Decimal("90000")),
            )
        assert exc_info.value.status_code == 422

    def test_revise_pending_offer_moves_to_negotiating(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline()
        offer = _make_offer(response="pending")
        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        with patch.object(svc, "_record_event"):
            with patch.object(svc, "_enrich", side_effect=lambda o: o):
                svc.revise_offer(
                    offer.id, pipeline.id, pipeline.organization_id,
                    _make_user(), OfferRevise(offered_salary=Decimal("95000")),
                )

        assert offer.offer_response == OfferResponse.NEGOTIATING.value
        assert offer.offered_salary == Decimal("95000")

    def test_revise_with_no_changes_returns_early(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline()
        offer = _make_offer(response="pending")
        # Make all proposed values identical to current.
        offer.offered_salary = Decimal("80000")
        offer.currency = "USD"
        offer.expiry_date = NEXT_WEEK

        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()

        with patch.object(svc, "_enrich", side_effect=lambda o: o):
            svc.revise_offer(
                offer.id, pipeline.id, pipeline.organization_id,
                _make_user(),
                OfferRevise(offered_salary=Decimal("80000"), currency="USD", expiry_date=NEXT_WEEK),
            )

        # No DB write if nothing changed.
        db.add.assert_not_called()

    def test_revise_resets_expiry_alert_on_date_change(self):
        svc, db = self._make_service()
        pipeline = _make_pipeline()
        offer = _make_offer(response="negotiating")
        offer.expiry_alert_sent = True
        offer.expiry_date = TOMORROW

        svc._get_pipeline = MagicMock(return_value=pipeline)
        svc._get_offer = MagicMock(return_value=offer)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        with patch.object(svc, "_record_event"):
            with patch.object(svc, "_enrich", side_effect=lambda o: o):
                svc.revise_offer(
                    offer.id, pipeline.id, pipeline.organization_id,
                    _make_user(),
                    OfferRevise(expiry_date=TODAY + timedelta(days=14)),
                )

        assert offer.expiry_alert_sent is False


# ── AIR-533: Expiry Alert Tests ───────────────────────────────────────────────

class TestExpiryAlerts:
    def _make_service(self, offers_to_return):
        db = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = offers_to_return
        db.scalars.return_value = mock_scalars
        db.add = MagicMock()
        db.commit = MagicMock()

        svc = OfferService.__new__(OfferService)
        svc.db = db
        return svc, db

    def test_expiry_alert_sent_for_approaching_offer(self):
        offer = _make_offer(response="pending", expiry_days=2)
        svc, db = self._make_service([offer])

        with patch("app.services.offer_service._notify_expiry_alert"):
            count = svc.process_expiry_alerts()

        assert count == 1
        assert offer.expiry_alert_sent is True
        db.commit.assert_called()

    def test_expiry_alert_sent_for_today_expiry(self):
        offer = _make_offer(response="pending", expiry_days=0)
        svc, db = self._make_service([offer])

        with patch("app.services.offer_service._notify_expiry_alert"):
            count = svc.process_expiry_alerts()

        assert count == 1

    def test_expiry_alert_sent_for_overdue_offer(self):
        offer = _make_offer(response="pending", expiry_days=-1)
        svc, db = self._make_service([offer])

        with patch("app.services.offer_service._notify_expiry_alert"):
            count = svc.process_expiry_alerts()

        assert count == 1

    def test_no_alerts_for_empty_result(self):
        svc, db = self._make_service([])
        count = svc.process_expiry_alerts()
        assert count == 0
        db.commit.assert_not_called()

    def test_expiry_alert_constant(self):
        assert EXPIRY_ALERT_DAYS_BEFORE == 3

    def test_individual_offer_failure_does_not_abort_batch(self):
        offer_ok = _make_offer(response="pending", expiry_days=1)
        offer_bad = _make_offer(response="pending", expiry_days=1)

        db = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [offer_bad, offer_ok]
        db.scalars.return_value = mock_scalars
        db.add = MagicMock()

        commit_calls = [0]

        def commit_side_effect():
            commit_calls[0] += 1
            if commit_calls[0] == 1:
                raise RuntimeError("DB error!")

        db.commit = MagicMock(side_effect=commit_side_effect)
        db.rollback = MagicMock()

        svc = OfferService.__new__(OfferService)
        svc.db = db

        with patch("app.services.offer_service._notify_expiry_alert"):
            count = svc.process_expiry_alerts()

        # Second offer still processed.
        assert count == 1


# ── AIR-533: Offer History Tests ──────────────────────────────────────────────

class TestOfferHistory:
    def test_record_event_creates_offer_event(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db

        offer = _make_offer()
        added_events = []
        db.add = lambda obj: added_events.append(obj)

        svc._record_event(
            offer=offer,
            event_type=OfferEventType.OFFER_CREATED,
            actor_user_id=uuid4(),
            new_response="pending",
            notes="Test event",
        )

        assert len(added_events) == 1
        event = added_events[0]
        from app.models.offer import PipelineOfferEvent
        assert isinstance(event, PipelineOfferEvent)
        assert event.event_type == OfferEventType.OFFER_CREATED.value

    def test_offer_events_include_all_lifecycle_types(self):
        """Verify all OfferEventType members are valid string values."""
        expected = {
            "offer_created", "offer_revised", "response_updated",
            "expiry_alert_sent", "offer_expired",
        }
        actual = {e.value for e in OfferEventType}
        assert actual == expected

    def test_offer_response_enum_covers_all_states(self):
        expected = {"pending", "accepted", "declined", "negotiating"}
        actual = {r.value for r in OfferResponse}
        assert actual == expected


# ── Org Scoping Tests ─────────────────────────────────────────────────────────

class TestOrgScoping:
    def test_offer_scoped_to_pipeline_organization(self):
        """get_offer raises 404 when offer belongs to different org."""
        db = MagicMock()
        db.scalar = MagicMock(return_value=None)  # Offer not found for this org.

        svc = OfferService.__new__(OfferService)
        svc.db = db
        svc._pipeline_svc = MagicMock()

        pipeline = _make_pipeline()
        wrong_org_id = uuid4()

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc._get_offer(uuid4(), pipeline.id, wrong_org_id)
        assert exc_info.value.status_code == 404

    def test_pipeline_scoping_delegated_to_pipeline_service(self):
        """_get_pipeline calls PipelineService which enforces org + access scope."""
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db
        svc._pipeline_svc = MagicMock()

        pipeline_id = uuid4()
        org_id = uuid4()
        user = _make_user(org_id=org_id)

        svc._get_pipeline(pipeline_id, org_id, user)
        svc._pipeline_svc.get_pipeline_by_id.assert_called_once_with(pipeline_id, org_id, user)


# ── Auto-transition Integration Tests ────────────────────────────────────────

class TestAutoTransition:
    """_auto_transition now goes through
    app.orchestration.pipeline_transitions.transition_pipeline_stage (a
    module-level orchestrator, called via a local import) rather than
    calling self._pipeline_svc.transition_stage directly — PlacementHistory
    is coordinated by that orchestrator, not by PipelineService itself. Mock
    at that boundary instead of on a PipelineService instance.
    """

    def test_auto_transition_uses_pipeline_service(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db

        from app.schemas.pipeline import PipelineStage

        pipeline = _make_pipeline()
        user = _make_user()
        org_id = pipeline.organization_id

        with patch("app.orchestration.pipeline_transitions.transition_pipeline_stage") as mock_transition:
            svc._auto_transition(
                pipeline=pipeline,
                organization_id=org_id,
                current_user=user,
                new_stage=PipelineStage.PLACED,
                reason="Offer accepted.",
            )

        mock_transition.assert_called_once()
        # transition_pipeline_stage(db, pipeline_id, organization_id, current_user, payload)
        args = mock_transition.call_args.args
        assert args[0] is db
        assert args[1] == pipeline.id
        assert args[2] == org_id
        assert args[4].stage == PipelineStage.PLACED

    def test_auto_transition_raises_500_on_failure(self):
        db = MagicMock()
        svc = OfferService.__new__(OfferService)
        svc.db = db

        from app.schemas.pipeline import PipelineStage
        from fastapi import HTTPException

        with patch(
            "app.orchestration.pipeline_transitions.transition_pipeline_stage",
            side_effect=RuntimeError("DB error"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                svc._auto_transition(
                    pipeline=_make_pipeline(),
                    organization_id=uuid4(),
                    current_user=_make_user(),
                    new_stage=PipelineStage.PLACED,
                    reason="Test",
                )
        assert exc_info.value.status_code == 500


# ── Enrichment Tests ──────────────────────────────────────────────────────────

class TestEnrichment:
    def test_enrich_sets_days_until_expiry(self):
        offer = _make_offer(expiry_days=5)
        result = OfferService._enrich(offer)
        # MagicMock setattr via object.__setattr__ — check attribute was set.
        assert getattr(result, "days_until_expiry") == 5

    def test_enrich_sets_is_expired_false_for_future(self):
        offer = _make_offer(expiry_days=1)
        result = OfferService._enrich(offer)
        assert getattr(result, "is_expired") is False

    def test_enrich_sets_is_expired_true_for_past(self):
        offer = _make_offer(expiry_days=-3)
        result = OfferService._enrich(offer)
        assert getattr(result, "is_expired") is True

    def test_enrich_sets_zero_days_for_today(self):
        offer = _make_offer(expiry_days=0)
        result = OfferService._enrich(offer)
        assert getattr(result, "days_until_expiry") == 0
        assert getattr(result, "is_expired") is False  # today is not expired
