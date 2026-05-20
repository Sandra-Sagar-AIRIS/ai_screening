from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.candidate import CandidateCreate, CandidateUpdate
from app.services.access_scope_service import AccessScopeService


class CandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)

    def create_candidate(
        self,
        organization_id: UUID,
        payload: CandidateCreate,
        *,
        current_user: CurrentUser | None = None,
        auto_commit: bool = True,
    ) -> Candidate:
        """
        Create a candidate.

        Security: vendor access is enforced in query filters (list/get) by scoping to `created_by`.
        """
        created_by = UUID(current_user.user_id) if current_user is not None else None
        source_type = "vendor" if (current_user is not None and (current_user.role or "").strip().lower() == "vendor") else "internal"

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
            created_by=created_by,
            source_type=source_type,
        )
        self.db.add(candidate)
        if auto_commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(candidate)
        return candidate

    def list_candidates(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Candidate]:
        stmt: Select[tuple[Candidate]] = (
            select(Candidate)
            .where(
                or_(
                    Candidate.organization_id == organization_id,
                    Candidate.org_id == organization_id,
                ),
                Candidate.is_deleted.is_(False),
                Candidate.deleted_at.is_(None),
            )
            .order_by(Candidate.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if self._scope.is_client_user(current_user):
            stmt = stmt.where(
                Candidate.id.in_(
                    select(Pipeline.candidate_id).where(
                        Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user))
                    )
                )
            )
        elif self._scope.is_vendor_user(current_user):
            # Vendors can see only candidates they submitted.
            stmt = stmt.where(Candidate.created_by == UUID(current_user.user_id))
        return list(self.db.scalars(stmt))

    def get_candidate_by_id(self, candidate_id: UUID, organization_id: UUID, current_user: CurrentUser) -> Candidate:
        stmt: Select[tuple[Candidate]] = select(Candidate).where(
            Candidate.id == candidate_id,
            or_(
                Candidate.organization_id == organization_id,
                Candidate.org_id == organization_id,
            ),
            Candidate.is_deleted.is_(False),
            Candidate.deleted_at.is_(None),
        )
        if self._scope.is_client_user(current_user):
            stmt = stmt.where(
                Candidate.id.in_(
                    select(Pipeline.candidate_id).where(
                        Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user))
                    )
                )
            )
        elif self._scope.is_vendor_user(current_user):
            stmt = stmt.where(Candidate.created_by == UUID(current_user.user_id))
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
        current_user: CurrentUser,
        payload: CandidateUpdate,
    ) -> Candidate:
        candidate = self.get_candidate_by_id(candidate_id, organization_id, current_user)

        update_data = payload.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"] is not None:
            update_data["email"] = str(update_data["email"]).lower()

        for field, value in update_data.items():
            setattr(candidate, field, value)

        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

