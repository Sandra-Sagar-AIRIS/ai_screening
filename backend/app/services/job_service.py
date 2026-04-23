from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate, JobStatus, JobUpdate
from app.services.client_service import ClientService


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._clients = ClientService(db)

    def create_job(self, organization_id: UUID, payload: JobCreate) -> Job:
        self._clients.get_client_by_id(payload.client_id, organization_id)

        job = Job(
            organization_id=organization_id,
            client_id=payload.client_id,
            title=payload.title.strip(),
            description=payload.description,
            status=payload.status.value,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        status: JobStatus | None = None,
        client_id: UUID | None = None,
    ) -> list[Job]:
        stmt: Select[tuple[Job]] = select(Job).where(Job.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Job.status == status.value)
        if client_id is not None:
            stmt = stmt.where(Job.client_id == client_id)
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    def get_job_by_id(self, job_id: UUID, organization_id: UUID) -> Job:
        stmt: Select[tuple[Job]] = select(Job).where(
            Job.id == job_id,
            Job.organization_id == organization_id,
        )
        job = self.db.scalar(stmt)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found.",
            )
        return job

    def update_job(
        self,
        job_id: UUID,
        organization_id: UUID,
        payload: JobUpdate,
    ) -> Job:
        job = self.get_job_by_id(job_id, organization_id)

        update_data = payload.model_dump(exclude_unset=True)
        if "client_id" in update_data:
            new_client_id = update_data.pop("client_id")
            if new_client_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="client_id cannot be null.",
                )
            self._clients.get_client_by_id(new_client_id, organization_id)
            update_data["client_id"] = new_client_id

        if "title" in update_data and update_data["title"] is not None:
            update_data["title"] = str(update_data["title"]).strip()
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value

        for field, value in update_data.items():
            setattr(job, field, value)

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
