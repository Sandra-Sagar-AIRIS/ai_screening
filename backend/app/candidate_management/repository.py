from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.candidate_management.models import (
    BulkUploadItem,
    BulkUploadItemStatus,
    BulkUploadJob,
    BulkUploadStatus,
    Candidate,
    CandidateAuditLog,
    CandidateInteraction,
    CandidateSkill,
    CandidateSource,
    CandidateStatus,
)


@dataclass(slots=True)
class CandidateSearchFilters:
    skills: list[str] | None = None
    location: str | None = None
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    status: CandidateStatus | None = None
    stage: str | None = None
    source: CandidateSource | None = None
    job_id: UUID | None = None
    include_deleted: bool = False


class CandidateRepository:
    """Data-access layer for candidate-management module."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -------------------------------
    # Candidate CRUD and retrieval
    # -------------------------------
    def create_candidate(self, candidate: Candidate) -> Candidate:
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def list_candidates_by_ids(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        candidate_ids: list[UUID],
        include_deleted: bool = False,
        with_skills: bool = True,
        for_update: bool = False,
    ) -> list[Candidate]:
        if not candidate_ids:
            return []
        stmt: Select[tuple[Candidate]] = select(Candidate).where(
            Candidate.org_id == org_id,
            Candidate.workspace_id == workspace_id,
            Candidate.id.in_(candidate_ids),
        )
        if not include_deleted:
            stmt = stmt.where(Candidate.deleted_at.is_(None))
        if with_skills:
            stmt = stmt.options(selectinload(Candidate.skills))
        if for_update:
            stmt = stmt.with_for_update()
        return list(self.db.scalars(stmt).unique())

    def get_candidate_by_id(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        candidate_id: UUID,
        include_deleted: bool = False,
        with_skills: bool = True,
        for_update: bool = False,
    ) -> Candidate | None:
        stmt: Select[tuple[Candidate]] = select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.org_id == org_id,
            Candidate.workspace_id == workspace_id,
        )
        if not include_deleted:
            stmt = stmt.where(Candidate.deleted_at.is_(None))
        if with_skills:
            stmt = stmt.options(selectinload(Candidate.skills))
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def list_candidates(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        limit: int,
        offset: int,
        filters: CandidateSearchFilters | None = None,
    ) -> list[Candidate]:
        filters = filters or CandidateSearchFilters()
        stmt: Select[tuple[Candidate]] = (
            select(Candidate)
            .options(selectinload(Candidate.skills))
            .where(
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
            )
            .order_by(Candidate.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        stmt = self._apply_candidate_filters(stmt, filters)
        return list(self.db.scalars(stmt).unique())

    def count_candidates(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        filters: CandidateSearchFilters | None = None,
    ) -> int:
        filters = filters or CandidateSearchFilters()
        stmt: Select[tuple[int]] = (
            select(func.count(func.distinct(Candidate.id)))
            .select_from(Candidate)
            .where(
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
            )
        )
        stmt = self._apply_candidate_filters(stmt, filters)
        return int(self.db.scalar(stmt) or 0)

    def update_candidate_fields(self, candidate: Candidate, updates: dict[str, Any]) -> Candidate:
        for field, value in updates.items():
            setattr(candidate, field, value)
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def soft_delete_candidate(self, *, candidate: Candidate, deleted_by: UUID | None) -> Candidate:
        candidate.deleted_at = datetime.now(timezone.utc)
        candidate.deleted_by = deleted_by
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def restore_candidate(self, *, candidate: Candidate) -> Candidate:
        candidate.deleted_at = None
        candidate.deleted_by = None
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def hard_delete_candidate(self, *, org_id: UUID, workspace_id: UUID, candidate_id: UUID) -> int:
        stmt = (
            delete(Candidate)
            .where(
                Candidate.id == candidate_id,
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
            )
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    # -------------------------------
    # Duplicate detection
    # -------------------------------
    def find_duplicate_candidate(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        email: str | None,
        phone: str | None,
        exclude_candidate_id: UUID | None = None,
    ) -> Candidate | None:
        comparisons = []
        if email:
            comparisons.append(func.lower(Candidate.email) == email.lower())
        if phone:
            comparisons.append(Candidate.phone == phone)
        if not comparisons:
            return None

        stmt: Select[tuple[Candidate]] = (
            select(Candidate)
            .where(
                Candidate.org_id == org_id,
                Candidate.workspace_id == workspace_id,
                Candidate.deleted_at.is_(None),
                or_(*comparisons),
            )
            .order_by(Candidate.created_at.asc())
        )
        if exclude_candidate_id is not None:
            stmt = stmt.where(Candidate.id != exclude_candidate_id)
        return self.db.scalar(stmt)

    # -------------------------------
    # Skills
    # -------------------------------
    def replace_candidate_skills(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        candidate_id: UUID,
        skills: list[CandidateSkill],
    ) -> list[CandidateSkill]:
        self.db.execute(
            delete(CandidateSkill).where(
                CandidateSkill.org_id == org_id,
                CandidateSkill.workspace_id == workspace_id,
                CandidateSkill.candidate_id == candidate_id,
            )
        )
        for skill in skills:
            self.db.add(skill)
        self.db.flush()
        return skills

    def list_candidate_skills(self, *, org_id: UUID, workspace_id: UUID, candidate_id: UUID) -> list[CandidateSkill]:
        stmt: Select[tuple[CandidateSkill]] = (
            select(CandidateSkill)
            .where(
                CandidateSkill.org_id == org_id,
                CandidateSkill.workspace_id == workspace_id,
                CandidateSkill.candidate_id == candidate_id,
            )
            .order_by(CandidateSkill.normalized_name.asc())
        )
        return list(self.db.scalars(stmt))

    def add_candidate_skills(self, skills: list[CandidateSkill]) -> list[CandidateSkill]:
        for skill in skills:
            self.db.add(skill)
        self.db.flush()
        return skills

    # -------------------------------
    # Interactions (append-only)
    # -------------------------------
    def create_interaction(self, interaction: CandidateInteraction) -> CandidateInteraction:
        self.db.add(interaction)
        self.db.flush()
        return interaction

    def list_interactions(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        candidate_id: UUID,
        limit: int,
        offset: int,
    ) -> list[CandidateInteraction]:
        stmt: Select[tuple[CandidateInteraction]] = (
            select(CandidateInteraction)
            .where(
                CandidateInteraction.org_id == org_id,
                CandidateInteraction.workspace_id == workspace_id,
                CandidateInteraction.candidate_id == candidate_id,
            )
            .order_by(CandidateInteraction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    # -------------------------------
    # Audit log (insert-only)
    # -------------------------------
    def create_audit_log(self, audit_log: CandidateAuditLog) -> CandidateAuditLog:
        self.db.add(audit_log)
        self.db.flush()
        return audit_log

    def create_audit_logs(self, logs: list[CandidateAuditLog]) -> list[CandidateAuditLog]:
        for log in logs:
            self.db.add(log)
        self.db.flush()
        return logs

    # -------------------------------
    # Merge helpers
    # -------------------------------
    def merge_candidate_skills(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        source_candidate_id: UUID,
        target_candidate_id: UUID,
    ) -> None:
        source_skills = self.list_candidate_skills(
            org_id=org_id,
            workspace_id=workspace_id,
            candidate_id=source_candidate_id,
        )
        target_skill_names = {
            skill.normalized_name
            for skill in self.list_candidate_skills(
                org_id=org_id,
                workspace_id=workspace_id,
                candidate_id=target_candidate_id,
            )
        }
        to_create: list[CandidateSkill] = []
        for skill in source_skills:
            if skill.normalized_name in target_skill_names:
                continue
            to_create.append(
                CandidateSkill(
                    org_id=org_id,
                    workspace_id=workspace_id,
                    candidate_id=target_candidate_id,
                    name=skill.name,
                    normalized_name=skill.normalized_name,
                    proficiency=skill.proficiency,
                    years_experience=skill.years_experience,
                    confidence=skill.confidence,
                    source=skill.source,
                )
            )
        if to_create:
            self.add_candidate_skills(to_create)

    def reassign_interactions(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        source_candidate_id: UUID,
        target_candidate_id: UUID,
    ) -> int:
        stmt = (
            update(CandidateInteraction)
            .where(
                CandidateInteraction.org_id == org_id,
                CandidateInteraction.workspace_id == workspace_id,
                CandidateInteraction.candidate_id == source_candidate_id,
            )
            .values(candidate_id=target_candidate_id)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def reassign_bulk_upload_items_candidate(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        source_candidate_id: UUID,
        target_candidate_id: UUID,
    ) -> int:
        stmt = (
            update(BulkUploadItem)
            .where(
                BulkUploadItem.org_id == org_id,
                BulkUploadItem.workspace_id == workspace_id,
                BulkUploadItem.candidate_id == source_candidate_id,
            )
            .values(candidate_id=target_candidate_id)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def mark_candidate_as_merged(
        self,
        *,
        source_candidate: Candidate,
        target_candidate_id: UUID,
        actor_user_id: UUID | None,
    ) -> Candidate:
        source_candidate.merged_into_candidate_id = target_candidate_id
        source_candidate.merged_at = datetime.now(timezone.utc)
        source_candidate.deleted_by = actor_user_id
        source_candidate.deleted_at = datetime.now(timezone.utc)
        self.db.add(source_candidate)
        self.db.flush()
        return source_candidate

    # -------------------------------
    # Bulk upload jobs/items
    # -------------------------------
    def create_bulk_upload_job(self, job: BulkUploadJob) -> BulkUploadJob:
        self.db.add(job)
        self.db.flush()
        return job

    def create_bulk_upload_items(self, items: list[BulkUploadItem]) -> list[BulkUploadItem]:
        for item in items:
            self.db.add(item)
        self.db.flush()
        return items

    def get_bulk_upload_job(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        job_id: UUID,
        with_items: bool = True,
    ) -> BulkUploadJob | None:
        stmt: Select[tuple[BulkUploadJob]] = select(BulkUploadJob).where(
            BulkUploadJob.id == job_id,
            BulkUploadJob.org_id == org_id,
            BulkUploadJob.workspace_id == workspace_id,
        )
        if with_items:
            stmt = stmt.options(selectinload(BulkUploadJob.items))
        return self.db.scalar(stmt)

    def list_bulk_upload_items(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        job_id: UUID,
        statuses: list[BulkUploadItemStatus] | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[BulkUploadItem]:
        stmt: Select[tuple[BulkUploadItem]] = (
            select(BulkUploadItem)
            .where(
                BulkUploadItem.org_id == org_id,
                BulkUploadItem.workspace_id == workspace_id,
                BulkUploadItem.job_id == job_id,
            )
            .order_by(BulkUploadItem.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        if statuses:
            stmt = stmt.where(BulkUploadItem.status.in_(statuses))
        return list(self.db.scalars(stmt))

    def update_bulk_upload_job_status(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        job_id: UUID,
        status: BulkUploadStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_summary: str | None = None,
    ) -> int:
        values: dict[str, Any] = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if error_summary is not None:
            values["error_summary"] = error_summary

        stmt = (
            update(BulkUploadJob)
            .where(
                BulkUploadJob.id == job_id,
                BulkUploadJob.org_id == org_id,
                BulkUploadJob.workspace_id == workspace_id,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def update_bulk_upload_job_counters(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        job_id: UUID,
        processed_delta: int = 0,
        success_delta: int = 0,
        failed_delta: int = 0,
        skipped_delta: int = 0,
    ) -> int:
        stmt = (
            update(BulkUploadJob)
            .where(
                BulkUploadJob.id == job_id,
                BulkUploadJob.org_id == org_id,
                BulkUploadJob.workspace_id == workspace_id,
            )
            .values(
                processed_items=BulkUploadJob.processed_items + processed_delta,
                success_items=BulkUploadJob.success_items + success_delta,
                failed_items=BulkUploadJob.failed_items + failed_delta,
                skipped_items=BulkUploadJob.skipped_items + skipped_delta,
            )
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def update_bulk_upload_item(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        item_id: UUID,
        values: dict[str, Any],
    ) -> int:
        stmt = (
            update(BulkUploadItem)
            .where(
                BulkUploadItem.id == item_id,
                BulkUploadItem.org_id == org_id,
                BulkUploadItem.workspace_id == workspace_id,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        return int(result.rowcount or 0)

    def get_bulk_upload_item(
        self,
        *,
        org_id: UUID,
        workspace_id: UUID,
        item_id: UUID,
    ) -> BulkUploadItem | None:
        stmt: Select[tuple[BulkUploadItem]] = select(BulkUploadItem).where(
            BulkUploadItem.id == item_id,
            BulkUploadItem.org_id == org_id,
            BulkUploadItem.workspace_id == workspace_id,
        )
        return self.db.scalar(stmt)

    # -------------------------------
    # Internal query composition
    # -------------------------------
    def _apply_candidate_filters(self, stmt: Select, filters: CandidateSearchFilters) -> Select:
        if not filters.include_deleted:
            stmt = stmt.where(Candidate.deleted_at.is_(None))
        if filters.status is not None:
            stmt = stmt.where(Candidate.status == filters.status)
        if filters.stage is not None:
            stmt = stmt.where(Candidate.stage == filters.stage)
        if filters.source is not None:
            stmt = stmt.where(Candidate.source == filters.source)
        if filters.job_id is not None:
            stmt = stmt.where(Candidate.job_id == filters.job_id)

        conditions = []
        if filters.location:
            conditions.append(Candidate.location.ilike(f"%{filters.location}%"))
        if filters.min_years_experience is not None:
            conditions.append(Candidate.years_experience >= filters.min_years_experience)
        if filters.max_years_experience is not None:
            conditions.append(Candidate.years_experience <= filters.max_years_experience)

        if filters.skills:
            normalized = [skill.strip().lower() for skill in filters.skills if skill.strip()]
            if normalized:
                stmt = stmt.join(
                    CandidateSkill,
                    and_(
                        CandidateSkill.candidate_id == Candidate.id,
                        CandidateSkill.org_id == Candidate.org_id,
                        CandidateSkill.workspace_id == Candidate.workspace_id,
                    ),
                ).where(CandidateSkill.normalized_name.in_(normalized))

        if conditions:
            stmt = stmt.where(*conditions)
        return stmt

