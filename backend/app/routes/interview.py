from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import (
    INTERVIEWS_CLAIM,
    INTERVIEWS_CREATE,
    INTERVIEWS_DELETE,
    INTERVIEWS_FEEDBACK,
    INTERVIEWS_PANEL,
    INTERVIEWS_READ,
    INTERVIEWS_UPDATE,
)
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.interview import (
    InterviewCreate,
    InterviewFeedbackCreate,
    InterviewFeedbackResponse,
    InterviewParticipantCreate,
    InterviewParticipantResponse,
    InterviewResponse,
    InterviewUpdate,
    InterviewerProfileCreate,
    InterviewerProfileResponse,
    NoteResponse,
    NoteUpsert,
    QueueInterviewResponse,
    WorkspaceResponse,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["interviews"])


# ── Create / List ────────────────────────────────────────────────────────

@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.create_interview(UUID(current_user.organization_id), current_user, payload)
    return InterviewResponse.model_validate(interview)


@router.get("", response_model=list[InterviewResponse])
def list_interviews(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    pipeline_id: Annotated[UUID | None, Query()] = None,
    candidate_id: Annotated[UUID | None, Query()] = None,
    job_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[InterviewResponse]:
    svc = InterviewService(db)
    interviews = svc.list_interviews(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        pipeline_id=pipeline_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status_filter=status_filter,
    )
    return [InterviewResponse.model_validate(i) for i in interviews]


# ── Queue (interviews needing panelists) ─────────────────────────────────

@router.get("/queue", response_model=list[QueueInterviewResponse])
def get_interview_queue(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    round_type: Annotated[str | None, Query()] = None,
    job_id: Annotated[UUID | None, Query()] = None,
) -> list[QueueInterviewResponse]:
    svc = InterviewService(db)
    return svc.get_queue(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        round_type=round_type,
        job_id=job_id,
    )


# ── My Interviews ────────────────────────────────────────────────────────

@router.get("/my", response_model=list[InterviewResponse])
def get_my_interviews(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InterviewResponse]:
    svc = InterviewService(db)
    interviews = svc.get_my_interviews(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
    )
    return [InterviewResponse.model_validate(i) for i in interviews]


# ── Single interview ─────────────────────────────────────────────────────

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.get_interview_by_id(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewResponse.model_validate(interview)


@router.patch("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: UUID,
    payload: InterviewUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.update_interview(
        interview_id=interview_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return InterviewResponse.model_validate(interview)


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview_put(
    interview_id: UUID,
    payload: InterviewUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.update_interview(
        interview_id=interview_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return InterviewResponse.model_validate(interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_DELETE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    svc = InterviewService(db)
    svc.delete_interview(interview_id, UUID(current_user.organization_id), current_user)


# ── Claim (self-assign as panelist) ─────────────────────────────────────

@router.post("/{interview_id}/claim", response_model=InterviewParticipantResponse, status_code=status.HTTP_201_CREATED)
def claim_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_CLAIM))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewParticipantResponse:
    svc = InterviewService(db)
    participant = svc.claim_interview(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewParticipantResponse.model_validate(participant)


# ── Participants ─────────────────────────────────────────────────────────

@router.get("/{interview_id}/participants", response_model=list[InterviewParticipantResponse])
def list_participants(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[InterviewParticipantResponse]:
    svc = InterviewService(db)
    participants = svc.list_participants(interview_id, UUID(current_user.organization_id), current_user)
    return [InterviewParticipantResponse.model_validate(p) for p in participants]


@router.post("/{interview_id}/participants", response_model=InterviewParticipantResponse, status_code=status.HTTP_201_CREATED)
def add_participant(
    interview_id: UUID,
    payload: InterviewParticipantCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_PANEL))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewParticipantResponse:
    svc = InterviewService(db)
    participant = svc.add_participant(interview_id, UUID(current_user.organization_id), current_user, payload)
    return InterviewParticipantResponse.model_validate(participant)


@router.delete("/{interview_id}/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    interview_id: UUID,
    participant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_PANEL))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    svc = InterviewService(db)
    svc.remove_participant(interview_id, participant_id, UUID(current_user.organization_id), current_user)


# ── Feedback ─────────────────────────────────────────────────────────────

@router.post(
    "/{interview_id}/feedback",
    response_model=InterviewFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    interview_id: UUID,
    payload: InterviewFeedbackCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_FEEDBACK))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewFeedbackResponse:
    svc = InterviewService(db)
    feedback = svc.create_feedback(
        interview_id=interview_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return InterviewFeedbackResponse.model_validate(feedback)


@router.get("/{interview_id}/feedback", response_model=list[InterviewFeedbackResponse])
def get_feedback(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[InterviewFeedbackResponse]:
    svc = InterviewService(db)
    feedback_list = svc.get_feedback(
        interview_id=interview_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [InterviewFeedbackResponse.model_validate(f) for f in feedback_list]


# ── Interviewer Profile ───────────────────────────────────────────────────

@router.get("/profile/me", response_model=InterviewerProfileResponse | None)
def get_my_profile(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewerProfileResponse | None:
    svc = InterviewService(db)
    profile = svc.get_my_profile(UUID(current_user.organization_id), current_user)
    if profile is None:
        return None
    resp = InterviewerProfileResponse.model_validate(profile)
    resp.skills = svc.get_profile_skills(profile.id)
    return resp


@router.put("/profile/me", response_model=InterviewerProfileResponse)
def upsert_my_profile(
    payload: InterviewerProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewerProfileResponse:
    svc = InterviewService(db)
    profile = svc.upsert_my_profile(UUID(current_user.organization_id), current_user, payload)
    resp = InterviewerProfileResponse.model_validate(profile)
    resp.skills = svc.get_profile_skills(profile.id)
    return resp


# ── Workspace ─────────────────────────────────────────────────────────────

@router.get("/{interview_id}/workspace", response_model=WorkspaceResponse)
def get_workspace(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> WorkspaceResponse:
    svc = InterviewService(db)
    return svc.get_workspace(interview_id, UUID(current_user.organization_id), current_user)


# ── Notes ─────────────────────────────────────────────────────────────────

@router.get("/{interview_id}/notes", response_model=list[NoteResponse])
def get_notes(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[NoteResponse]:
    svc = InterviewService(db)
    notes = svc.get_notes(interview_id, UUID(current_user.organization_id), current_user)
    return [NoteResponse.model_validate(n) for n in notes]


@router.patch("/{interview_id}/notes", response_model=NoteResponse)
def upsert_note(
    interview_id: UUID,
    payload: NoteUpsert,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> NoteResponse:
    svc = InterviewService(db)
    note = svc.upsert_note(interview_id, UUID(current_user.organization_id), current_user, payload)
    return NoteResponse.model_validate(note)


# ── Status controls ───────────────────────────────────────────────────────

@router.post("/{interview_id}/start", response_model=InterviewResponse)
def start_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.start_interview(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewResponse.model_validate(interview)


@router.post("/{interview_id}/complete", response_model=InterviewResponse)
def complete_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.complete_interview(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewResponse.model_validate(interview)


@router.post("/{interview_id}/no-show", response_model=InterviewResponse)
def mark_no_show(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    svc = InterviewService(db)
    interview = svc.mark_no_show(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewResponse.model_validate(interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_DELETE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    svc = InterviewService(db)
    svc.delete_interview(interview_id, UUID(current_user.organization_id), current_user)



