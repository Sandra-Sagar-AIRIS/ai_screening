from typing import Annotated
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.schemas.auth import CurrentUser

class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application(self, organization_id: UUID, current_user: CurrentUser, payload: ApplicationCreate) -> Application:
        existing = self.db.scalar(
            select(Application).where(
                Application.organization_id == organization_id,
                Application.candidate_id == payload.candidate_id,
                Application.job_id == payload.job_id,
            )
        )
        if existing:
            return existing

        app = Application(
            organization_id=organization_id,
            candidate_id=payload.candidate_id,
            job_id=payload.job_id,
            stage="applied",
            status="active"
        )
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def update_application(self, application_id: UUID, organization_id: UUID, current_user: CurrentUser, payload: ApplicationUpdate) -> Application:
        app = self.db.scalar(
            select(Application).where(
                Application.id == application_id,
                Application.organization_id == organization_id,
            )
        )
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        if payload.stage is not None:
            app.stage = payload.stage
        if payload.status is not None:
            app.status = payload.status
        if payload.notes is not None:
            app.notes = payload.notes

        self.db.commit()
        self.db.refresh(app)
        return app
