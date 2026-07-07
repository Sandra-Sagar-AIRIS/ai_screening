"""Orchestrates Interview <-> Pipeline coordination.

InterviewService no longer imports or instantiates PipelineService (see
app/services/interview_service.py). Both call sites that used to reach
into the Pipeline domain from inside InterviewService are here instead:
fetching/validating a pipeline is a Pipeline-domain concern, so it goes
through PipelineService, and the result is handed to InterviewService as
plain data.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.schemas.auth import CurrentUser
from app.schemas.interview import InterviewCreate, InterviewUpdate
from app.services.interview_service import InterviewService
from app.services.pipeline_service import PipelineService


def create_interview(
    db: Session,
    organization_id: UUID,
    current_user: CurrentUser,
    payload: InterviewCreate,
) -> Interview:
    pipeline = PipelineService(db).get_pipeline_by_id(payload.pipeline_id, organization_id, current_user)
    return InterviewService(db).create_interview(organization_id, current_user, payload, pipeline=pipeline)


def update_interview(
    db: Session,
    interview_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    payload: InterviewUpdate,
) -> Interview:
    update_data = payload.model_dump(exclude_unset=True)
    if "pipeline_id" in update_data:
        new_pipeline_id = update_data["pipeline_id"]
        if new_pipeline_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pipeline_id cannot be null.")
        # Validate existence/access before InterviewService applies the update
        # (identical check InterviewService used to perform internally).
        PipelineService(db).get_pipeline_by_id(new_pipeline_id, organization_id, current_user)

    return InterviewService(db).update_interview(
        interview_id=interview_id,
        organization_id=organization_id,
        current_user=current_user,
        payload=payload,
    )
