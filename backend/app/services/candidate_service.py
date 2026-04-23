from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_candidate(self, organization_id: UUID, payload: CandidateCreate) -> Candidate:
        candidate = Candidate(
            organization_id=organization_id,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=str(payload.email).lower(),
            phone=payload.phone,
            location=payload.location,
            experience_summary=payload.experience_summary,
            education=payload.education,
            notes=payload.notes,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def list_candidates(self, organization_id: UUID, limit: int = 50, offset: int = 0) -> list[Candidate]:
        stmt: Select[tuple[Candidate]] = (
            select(Candidate)
            .where(
                Candidate.organization_id == organization_id,
                Candidate.is_deleted.is_(False),
            )
            .order_by(Candidate.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def get_candidate_by_id(self, candidate_id: UUID, organization_id: UUID) -> Candidate:
        stmt: Select[tuple[Candidate]] = select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.organization_id == organization_id,
            Candidate.is_deleted.is_(False),
        )
        candidate = self.db.scalar(stmt)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found.",
            )
        return candidate

    def update_candidate(
        self,
        candidate_id: UUID,
        organization_id: UUID,
        payload: CandidateUpdate,
    ) -> Candidate:
        candidate = self.get_candidate_by_id(candidate_id, organization_id)

        update_data = payload.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"] is not None:
            update_data["email"] = str(update_data["email"]).lower()

        for field, value in update_data.items():
            setattr(candidate, field, value)

        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

