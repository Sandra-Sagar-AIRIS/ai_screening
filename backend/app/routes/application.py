from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import PIPELINE_CREATE, PIPELINE_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.application import ApplicationCreate, ApplicationResponse, ApplicationUpdate
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ApplicationResponse:
    service = ApplicationService(db)
    app = service.create_application(UUID(current_user.organization_id), current_user, payload)
    return ApplicationResponse.model_validate(app)


@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: UUID,
    payload: ApplicationUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ApplicationResponse:
    service = ApplicationService(db)
    app = service.update_application(
        application_id=application_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return ApplicationResponse.model_validate(app)
