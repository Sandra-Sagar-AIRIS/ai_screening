from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
import sqlalchemy as sa
from sqlalchemy import Select, or_, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.candidate import Candidate
from app.models.candidate_job_match import CandidateJobMatch
from app.models.job_status_history import JobStatusHistory
from app.models.job_skill import JobSkill
from app.models.job_match_cache import JobMatchCache
from app.models.job_submission import JobSubmission
from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.job import (
    AtsPairStatusResponse,
    CandidateMatchEntry,
    CandidateMatchesResponse,
    HybridScoreBreakdown,
    JobCreate,
    JobStatus,
    JobMatchEntry,
    JobMatchCategoryScores,
    JobMatchTriggerRequest,
    JobMatchTriggerResponse,
    JobMatchesResponse,
    JobSubmissionCreate,
    JobSubmissionResponse,
    JobSubmissionStatus,
    JobSubmissionStatusUpdate,
    JobUpdate,
    JobResponse,
)
from app.services.access_scope_service import AccessScopeService
from app.services.client_service import ClientService
from app.services.candidate_service import CandidateService
from app.services.jd_normalization_service import JDNormalizationService
from app.services.ats_matching_service import (
    ATSMatchingService,
    CandidateScoringInput,
    JobScoringInput,
)
from app.services.task_runner import dispatch_task
from app.services.semantic_matching_service import (
    SemanticMatchingService,
    build_condensed_candidate_job_payload,
    hybrid_match_score,
)
from app.core.config import get_settings
from app.services.ats_pair_cache import get_job_skills_cached, get_resume_extra_cached
from app.services.ats_pipeline_status import (
    ATS_AI_ENRICHING,
    ATS_COMPLETED,
    ATS_DETERMINISTIC_COMPLETE,
    ATS_FAILED,
    ATS_PARSING,
    ATS_PENDING,
    ATS_QUEUED,
    SEMANTIC_INFLIGHT_DEDUP_SECONDS,
)


logger = logging.getLogger(__name__)
DEV_MODE = True

class JobService:
    _ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
        JobStatus.DRAFT.value: {JobStatus.OPEN.value},
        JobStatus.OPEN.value: {JobStatus.CLOSED.value, JobStatus.FILLED.value, JobStatus.PAUSED.value},
        JobStatus.PAUSED.value: {JobStatus.OPEN.value},
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self._clients = ClientService(db)
        self._scope = AccessScopeService(db)
        self._candidates = CandidateService(db)
        self._jd_normalizer = JDNormalizationService()
        self._ats = ATSMatchingService()
        # Local import to avoid circular import with pipeline_service.
        from app.services.pipeline_service import PipelineService

        self._pipelines = PipelineService(db)

    def _get_job_response(self, job: Job) -> JobResponse:
        """Helper to construct JobResponse including skills (Task 4/1)."""
        required_skills = []
        preferred_skills = []
        try:
            skills = self.db.scalars(
                select(JobSkill).where(JobSkill.job_id == job.id)
            ).all()
            required_skills = [s.skill for s in skills if s.is_required]
            preferred_skills = [s.skill for s in skills if not s.is_required]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch job skills (migration missing?): {e}")
            self.db.rollback()
        
        return JobResponse(
            id=job.id,
            organization_id=job.organization_id,
            client_id=job.client_id,
            title=job.title,
            description=job.description,
            status=JobStatus(job.status),
            paused_reason=job.paused_reason,
            location=job.location,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            experience_min_years=job.experience_min_years,
            experience_max_years=job.experience_max_years,
            employment_type=job.employment_type,
            urgency=job.urgency,
            created_by=job.created_by,
            filled_at=job.filled_at,
            required_skills=required_skills or [],
            preferred_skills=preferred_skills or [],
            key_responsibilities=job.key_responsibilities or [],
            raw_jd_text=job.raw_jd_text,
            parsing_source=job.parsing_source,
            parsing_status=job.parsing_status,
            created_at=job.created_at,
            updated_at=job.updated_at
        )

    def get_or_create_default_client(self, organization_id: UUID):
        from app.models.client import Client
        client = self.db.scalars(
            select(Client).where(Client.organization_id == organization_id, Client.name == "Default Client")
        ).first()
        if not client:
            client = Client(organization_id=organization_id, name="Default Client")
            self.db.add(client)
            self.db.commit()
            self.db.refresh(client)
        return client

    def create_job(self, organization_id: UUID, payload: JobCreate, *, created_by: UUID | None = None) -> JobResponse:
        import logging
        logger = logging.getLogger(__name__)

        client_exists = False
        valid_client_id = None

        try:
            if payload.client_id:
                valid_client_id = UUID(str(payload.client_id))
                self._clients.get_client_by_id(valid_client_id, organization_id)
                client_exists = True
        except Exception as e:
            logger.warning(f"Error checking client: {str(e)}")
            client_exists = False

        if not client_exists:
            if DEV_MODE:
                logger.warning("Using default client for job creation (DEV MODE)")
                try:
                    default_client = self.get_or_create_default_client(organization_id)
                    payload.client_id = default_client.id
                except Exception as e:
                    logger.error(f"Error in job creation: {str(e)}")
                    raise HTTPException(status_code=400, detail="Unable to create default client. Check organization mapping.")
            else:
                logger.error(f"Error in job creation: Client not found for id {payload.client_id}")
                raise HTTPException(status_code=400, detail="Client not found")
        else:
            payload.client_id = valid_client_id

        if payload.salary_min is not None and payload.salary_max is not None and payload.salary_min > payload.salary_max:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_SALARY_RANGE"})
        if (
            payload.experience_min_years is not None
            and payload.experience_max_years is not None
            and payload.experience_min_years > payload.experience_max_years
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_EXPERIENCE_RANGE"},
            )

        job = Job(
            organization_id=organization_id,
            client_id=payload.client_id,
            title=payload.title.strip(),
            description=payload.description,
            # Product decision: new jobs should always start in "open".
            status=JobStatus.OPEN.value,
            location=payload.location,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            salary_currency=payload.salary_currency,
            experience_min_years=payload.experience_min_years,
            experience_max_years=payload.experience_max_years,
            employment_type=payload.employment_type,
            urgency=payload.urgency,
            key_responsibilities=payload.key_responsibilities,
            raw_jd_text=payload.raw_jd_text,
            parsing_source=payload.parsing_source,
            parsing_status=payload.parsing_status,
            created_by=created_by,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Store normalized job skills + record JD parsing lifecycle so the UI
        # can tell when ATS-ready data is present.
        if payload.required_skills or payload.preferred_skills:
            ok = self._upsert_job_skills(
                job_id=job.id,
                required_skills=payload.required_skills,
                preferred_skills=payload.preferred_skills,
            )
            job.parsing_status = "completed" if ok else "failed"
            self.db.add(job)
            self.db.commit()
            if ok:
                try:
                    from app.candidate_management.tasks_ats import rescore_job_task, run_rescore_job

                    dispatch_task(
                        task=rescore_job_task,
                        fallback=run_rescore_job,
                        kwargs={
                            "organization_id": str(organization_id),
                            "job_id": str(job.id),
                        },
                    )
                except Exception:
                    pass
        else:
            # No skills supplied yet — leave parsing_status empty/pending so the
            # caller can finalize it later (e.g. via /jobs/parse-jd).
            if job.parsing_status is None:
                job.parsing_status = "pending"
                self.db.add(job)
                self.db.commit()

        return self._get_job_response(job)

    def list_jobs(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        status: JobStatus | None = None,
        client_id: UUID | None = None,
    ) -> list[JobResponse]:
        stmt: Select[tuple[Job]] = select(Job).where(Job.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Job.status == status.value)
        elif (current_user.role or "").lower() == "recruiter":
            stmt = stmt.where(Job.status.in_([JobStatus.DRAFT.value, JobStatus.OPEN.value, JobStatus.PAUSED.value]))
        if client_id is not None:
            stmt = stmt.where(Job.client_id == client_id)
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Job.id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        jobs = list(self.db.scalars(stmt))
        return [self._get_job_response(job) for job in jobs]

    def get_job_by_id(self, job_id: UUID, organization_id: UUID, current_user: CurrentUser | None = None) -> Job:
        stmt: Select[tuple[Job]] = select(Job).where(
            Job.id == job_id,
            Job.organization_id == organization_id,
        )
        if current_user is not None and self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Job.id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        job = self.db.scalar(stmt)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found.",
            )
        return job
        
    def get_job_response_by_id(self, job_id: UUID, organization_id: UUID, current_user: CurrentUser | None = None) -> JobResponse:
        job = self.get_job_by_id(job_id, organization_id, current_user)
        return self._get_job_response(job)

    def update_job(
        self,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: JobUpdate,
    ) -> JobResponse:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"UPDATE_START: Job={job_id} Org={organization_id}")
        job = self.get_job_by_id(job_id, organization_id, current_user)

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use PATCH /jobs/{job_id}/status to change job status.",
            )

        # Validate salary/experience constraints against the *resulting* values.
        def _to_float(val: object) -> float | None:
            if val is None:
                return None
            try:
                return float(val)  # supports Decimal/numeric/float
            except Exception:  # noqa: BLE001
                return None

        salary_min = _to_float(update_data.get("salary_min", job.salary_min))
        salary_max = _to_float(update_data.get("salary_max", job.salary_max))
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_SALARY_RANGE"})

        exp_min = update_data.get("experience_min_years", job.experience_min_years)
        exp_max = update_data.get("experience_max_years", job.experience_max_years)
        if exp_min is not None and exp_max is not None and exp_min > exp_max:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_EXPERIENCE_RANGE"})

        # When job is marked as filled, persist `filled_at` for time-to-fill metrics.
        if update_data.get("status") == JobStatus.FILLED.value:
            job.filled_at = datetime.now(timezone.utc)

        # If skills are provided in an update, replace them fully.
        skills_touched = False
        if "required_skills" in update_data or "preferred_skills" in update_data:
            required_skills = update_data.pop("required_skills", None)
            preferred_skills = update_data.pop("preferred_skills", None)
            ok = self._upsert_job_skills(
                job_id=job.id,
                required_skills=required_skills,
                preferred_skills=preferred_skills,
            )
            update_data["parsing_status"] = "completed" if ok else "failed"
            skills_touched = True

        for field, value in update_data.items():
            setattr(job, field, value)

        # Hint downstream pipelines that this job's normalized requirements
        # changed; Phase 5 wires this to ATS rescoring.
        self._skills_changed_during_update = skills_touched

        try:
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            if skills_touched:
                try:
                    from app.candidate_management.tasks_ats import rescore_job_task, run_rescore_job

                    dispatch_task(
                        task=rescore_job_task,
                        fallback=run_rescore_job,
                        kwargs={
                            "organization_id": str(organization_id),
                            "job_id": str(job.id),
                        },
                    )
                except Exception:
                    pass
            logger.info(f"UPDATE_SUCCESS: Job {job.id} updated")
            return self._get_job_response(job)
        except Exception as e:
            logger.error(f"UPDATE_ERROR: {e}")
            raise


    def delete_job(self, job_id: UUID, organization_id: UUID, current_user: CurrentUser) -> None:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"DELETE_START: Job={job_id} Org={organization_id}")
        job = self.get_job_by_id(job_id, organization_id, current_user)
        try:
            self.db.delete(job)
            self.db.commit()
            logger.info(f"DELETE_SUCCESS: Job {job_id} deleted")
        except Exception as e:
            logger.error(f"DELETE_ERROR: {e}")
            self.db.rollback()
            raise

    def update_job_status(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        new_status: JobStatus,
        reason: str | None = None,
    ) -> JobResponse:
        job = self.get_job_by_id(job_id, organization_id, current_user)

        current_status = job.status
        target_status = new_status.value

        allowed_next = self._ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_next:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{target_status}'.",
            )

        if target_status == JobStatus.PAUSED.value and not (reason or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pause reason is required when moving a job to paused status.",
            )

        if target_status == JobStatus.FILLED.value:
            job.filled_at = datetime.now(timezone.utc)
        if target_status == JobStatus.PAUSED.value:
            job.paused_reason = (reason or "").strip()
        elif current_status == JobStatus.PAUSED.value and target_status == JobStatus.OPEN.value:
            job.paused_reason = None

        job.status = target_status
        self.db.add(
            JobStatusHistory(
                job_id=job.id,
                previous_status=current_status,
                new_status=target_status,
                changed_by=UUID(current_user.user_id),
                reason=(reason or "").strip() or None,
            )
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return self._get_job_response(job)

    def change_job_status(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        new_status: JobStatus,
    ) -> JobResponse:
        return self.update_job_status(
            job_id=job_id,
            organization_id=organization_id,
            current_user=current_user,
            new_status=new_status,
            reason=None,
        )

    def search_jobs(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        status_filter: JobStatus | None = None,
        urgency: str | None = None,
        location: str | None = None,
        skills: list[str] | None = None,
        client_id: UUID | None = None,
        min_experience: int | None = None, # Task 6
        max_experience: int | None = None, # Task 6
        salary_min: float | None = None,   # Task 6
        salary_max: float | None = None,   # Task 6
        employment_type: str | None = None, # Task 6
    ) -> list[JobResponse]:
        stmt: Select[tuple[Job]] = select(Job).where(Job.organization_id == organization_id)

        # Filters
        if status_filter is not None:
            stmt = stmt.where(Job.status == status_filter.value)
        if urgency:
            stmt = stmt.where(Job.urgency == urgency)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if client_id is not None:
            stmt = stmt.where(Job.client_id == client_id)
            
        # Task 6: New Filters
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)
        if min_experience is not None:
            stmt = stmt.where(Job.experience_min_years >= min_experience)
        if max_experience is not None:
            stmt = stmt.where(sa.or_(Job.experience_max_years <= max_experience, Job.experience_max_years.is_(None)))
        if salary_min is not None:
            stmt = stmt.where(Job.salary_min >= salary_min)
        if salary_max is not None:
            stmt = stmt.where(sa.or_(Job.salary_max <= salary_max, Job.salary_max.is_(None)))

        # AND logic: all required skills must be present in `job_skills` with is_required=true.
        if skills:
            normalized = [s.strip().lower() for s in skills if s and s.strip()]
            if normalized:
                stmt = (
                    stmt.join(
                        JobSkill,
                        sa.and_(
                            JobSkill.job_id == Job.id,
                            JobSkill.is_required.is_(True),
                        ),
                    )
                    .where(sa.func.lower(JobSkill.skill).in_(normalized))
                    .group_by(Job.id)
                    .having(sa.func.count(sa.func.distinct(sa.func.lower(JobSkill.skill))) == len(set(normalized)))
                )

        allowed_job_ids = self._scope.allowed_job_ids(current_user)
        if self._scope.is_client_user(current_user):
            if not allowed_job_ids:
                return []
            stmt = stmt.where(Job.id.in_(allowed_job_ids))

        # Urgency-first sorting when urgency filtering is used; else use newest first.
        if urgency is not None or status_filter is not None or location is not None or skills:
            stmt = stmt.order_by(
                sa.case(
                    (Job.urgency == "critical", 3),
                    (Job.urgency == "urgent", 2),
                    else_=1,
                ).desc(),
                Job.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(Job.created_at.desc())

        stmt = stmt.offset(offset).limit(limit)
        jobs = list(self.db.scalars(stmt))
        return [self._get_job_response(job) for job in jobs]

    # -------------------------------
    # Job submissions
    # -------------------------------
    def submit_candidate_to_job(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: JobSubmissionCreate,
    ) -> JobSubmissionResponse:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"SUBMIT_START: Job={job_id} Candidate={payload.candidate_id} Org={organization_id}")
        job = self.get_job_by_id(job_id, organization_id, current_user)

        # Candidate matching/pipeline submission is only valid for open jobs.
        if job.status != JobStatus.OPEN.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="JOB_NOT_OPEN")

        candidate = self._candidates.get_candidate_by_id(payload.candidate_id, organization_id, current_user)

        submitted_by = UUID(current_user.user_id)
        submission = JobSubmission(
            job_id=job.id,
            candidate_id=candidate.id,
            submitted_by=submitted_by,
            submission_status=JobSubmissionStatus.PENDING.value,
            notes=payload.notes,
        )
        self.db.add(submission)
        try:
            # Flush so we can create the pipeline in the same transaction.
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(
                select(JobSubmission).where(
                    JobSubmission.job_id == job.id,
                    JobSubmission.candidate_id == candidate.id,
                )
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "DUPLICATE_SUBMISSION",
                        "existing_submission_id": str(existing.id),
                        "existing_status": existing.submission_status,
                    },
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DUPLICATE_SUBMISSION")

        # Create initial pipeline card (Phase 1 integration).
        from app.schemas.pipeline import PipelineCreate, PipelineStage, PipelineStatus

        pipeline = self._pipelines.create_pipeline(
            organization_id=organization_id,
            current_user=current_user,
            payload=PipelineCreate(
                candidate_id=candidate.id,
                job_id=job.id,
                stage=PipelineStage.APPLIED,
                status=PipelineStatus.ACTIVE,
                notes=payload.notes,
            ),
            commit=False,
        )

        try:
            # Commit both JobSubmission and Pipeline together.
            self.db.commit()
            self.db.refresh(submission)
            try:
                from app.candidate_management.tasks_ats import (
                    rescore_candidate_job_task,
                    run_rescore_candidate_job,
                )

                dispatch_task(
                    task=rescore_candidate_job_task,
                    fallback=run_rescore_candidate_job,
                    kwargs={
                        "organization_id": str(organization_id),
                        "candidate_id": str(candidate.id),
                        "job_id": str(job.id),
                    },
                )
            except Exception as dispatch_exc:
                # Submission is already committed; never rollback here — only log dispatch noise.
                logger.warning(
                    "SUBMIT_ATS_DISPATCH_FAILED org=%s job=%s candidate=%s err=%s",
                    organization_id,
                    job.id,
                    candidate.id,
                    dispatch_exc,
                    exc_info=True,
                )
            res = JobSubmissionResponse.model_validate(submission)
            logger.info(f"SUBMIT_SUCCESS: Submission {submission.id} created")
            return res
        except Exception as e:
            logger.error(f"SUBMIT_VALIDATION_ERROR: {e}")
            raise


    def list_job_submissions(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        submission_status: JobSubmissionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobSubmissionResponse]:
        # Scope enforcement: if client user, ensure this job is in their allowed set.
        if self._scope.is_client_user(current_user):
            allowed_job_ids = self._scope.allowed_job_ids(current_user)
            if job_id not in set(allowed_job_ids):
                return []

        stmt: Select[tuple[JobSubmission]] = select(JobSubmission).where(
            JobSubmission.job_id == job_id,
        )
        if submission_status is not None:
            stmt = stmt.where(JobSubmission.submission_status == submission_status.value)
        stmt = stmt.order_by(JobSubmission.submitted_at.desc()).offset(offset).limit(limit)
        
        try:
            submissions = list(self.db.scalars(stmt))
            return [JobSubmissionResponse.model_validate(s) for s in submissions]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch submissions (migration missing?): {e}")
            self.db.rollback()
            return []

    def update_submission_status(
        self,
        *,
        job_id: UUID,
        submission_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: JobSubmissionStatusUpdate,
    ) -> JobSubmissionResponse:
        # Verify job access first
        job = self.get_job_by_id(job_id, organization_id, current_user)
        
        stmt = select(JobSubmission).where(
            JobSubmission.id == submission_id,
            JobSubmission.job_id == job.id
        )
        submission = self.db.scalar(stmt)
        
        if submission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job submission not found."
            )
            
        submission.submission_status = payload.submission_status.value
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return JobSubmissionResponse.model_validate(submission)


    def trigger_matching(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        request: JobMatchTriggerRequest,
    ) -> JobMatchTriggerResponse:
        refresh = request.refresh
        job = self.get_job_by_id(job_id, organization_id, current_user)
        cached = self._scalar_job_match_cache(job.id)
        if refresh or cached is None:
            self.rescore_job_sync(organization_id=organization_id, job_id=job.id)
            self.db.commit()
        cached = self._scalar_job_match_cache(job.id)
        generated_time = cached.generated_at if cached else datetime.now(timezone.utc)
        match_count = len(cached.ranked_candidate_ids or []) if cached else 0
        return JobMatchTriggerResponse(
            job_id=job.id,
            match_count=match_count,
            generated_at=generated_time,
            refresh_requested=refresh,
        )

    def get_candidate_matches(
        self,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        limit: int,
        offset: int,
        sort_by: str = "score_desc",
        min_score: int | None = None,
        recommendation: str | None = None,
    ) -> JobMatchesResponse:
        job = self.get_job_by_id(job_id, organization_id, current_user)
        filters = [
            CandidateJobMatch.organization_id == organization_id,
            CandidateJobMatch.job_id == job.id,
        ]
        if min_score is not None:
            filters.append(CandidateJobMatch.match_score >= min_score)
        if recommendation:
            filters.append(sa.func.lower(CandidateJobMatch.recommendation) == recommendation.lower())

        count_stmt = select(sa.func.count()).select_from(CandidateJobMatch).where(*filters)
        stmt = select(CandidateJobMatch).where(*filters)
        if sort_by == "missing_critical_asc":
            ms = CandidateJobMatch.missing_skills
            missing_len = sa.case(
                (ms.is_(None), 999_999),
                (sa.func.jsonb_typeof(ms) != sa.literal("array"), 999_999),
                else_=sa.func.jsonb_array_length(ms),
            )
            stmt = stmt.order_by(missing_len.asc(), CandidateJobMatch.match_score.desc())
        else:
            stmt = stmt.order_by(CandidateJobMatch.match_score.desc(), CandidateJobMatch.updated_at.desc())
        try:
            total_count = int(self.db.scalar(count_stmt) or 0)
            rows = list(self.db.scalars(stmt.offset(offset).limit(limit)))
        except ProgrammingError as exc:
            # ATS migrations may not be applied yet in some environments.
            # Return an empty payload instead of surfacing a 500 to recruiter UI.
            if "candidate_job_match" not in str(exc).lower():
                raise
            self.db.rollback()
            return JobMatchesResponse(
                job_id=job.id,
                matches=[],
                total_count=0,
                generated_at=job.updated_at,
                limit=limit,
                offset=offset,
            )
        submitted_ids = set(
            self.db.scalars(
                select(JobSubmission.candidate_id).where(
                    JobSubmission.job_id == job.id,
                    JobSubmission.candidate_id.in_([row.candidate_id for row in rows]),
                )
            )
        ) if rows else set()
        candidate_names: dict[UUID, str] = {}
        if rows:
            candidate_rows = self.db.execute(
                select(Candidate.id, Candidate.first_name, Candidate.last_name).where(
                    or_(
                        Candidate.organization_id == organization_id,
                        Candidate.org_id == organization_id,
                    ),
                    Candidate.id.in_([row.candidate_id for row in rows]),
                )
            ).all()
            for candidate_id, first_name, last_name in candidate_rows:
                full_name = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
                candidate_names[candidate_id] = full_name or str(candidate_id)
        matches: list[JobMatchEntry] = []
        for idx, row in enumerate(rows):
            cs = self._coerce_match_category_scores(row.category_scores)
            matches.append(
                JobMatchEntry(
                    rank=offset + idx + 1,
                    candidate_id=row.candidate_id,
                    candidate_name=candidate_names.get(row.candidate_id),
                    fit_score=row.match_score,
                    deterministic_match_score=getattr(row, "deterministic_match_score", None),
                    semantic_match_score=getattr(row, "semantic_match_score", None),
                    ai_enrichment_status=getattr(row, "ai_enrichment_status", None),
                    ats_pipeline_status=getattr(row, "ats_pipeline_status", None),
                    enrichment_started_at=getattr(row, "enrichment_started_at", None),
                    deterministic_completed_at=getattr(row, "deterministic_completed_at", None),
                    semantic_completed_at=getattr(row, "semantic_completed_at", None),
                    enrichment_error=getattr(row, "enrichment_error", None),
                    recruiter_summary=getattr(row, "recruiter_summary", None),
                    confidence_reasoning=getattr(row, "confidence_reasoning", None),
                    semantic_skill_matches=self._coerce_jsonb_str_list(
                        getattr(row, "semantic_skill_matches", None)
                    ),
                    transferable_skills=self._coerce_jsonb_str_list(getattr(row, "transferable_skills", None)),
                    inferred_strengths=self._coerce_jsonb_str_list(getattr(row, "inferred_strengths", None)),
                    inferred_gaps=self._coerce_jsonb_str_list(getattr(row, "inferred_gaps", None)),
                    category_scores=JobService._match_category_scores_model(cs),
                    already_submitted=row.candidate_id in submitted_ids,
                    matched_skills=self._coerce_jsonb_str_list(row.matched_skills),
                    missing_skills=self._coerce_jsonb_str_list(row.missing_skills),
                    recommendation=row.recommendation,
                    confidence_score=float(row.confidence_score or 0),
                    evaluated_at=getattr(row, "evaluated_at", None),
                )
            )
        cached = self._scalar_job_match_cache(job.id)
        return JobMatchesResponse(
            job_id=job.id,
            matches=matches,
            total_count=total_count,
            generated_at=(cached.generated_at if cached is not None else job.updated_at),
            limit=limit,
            offset=offset,
        )

    def get_candidate_matches(
        self,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        limit: int,
        offset: int,
    ) -> CandidateMatchesResponse:
        self._candidates.get_candidate_by_id(candidate_id, organization_id, current_user)
        filters = [
            CandidateJobMatch.organization_id == organization_id,
            CandidateJobMatch.candidate_id == candidate_id,
        ]
        count_stmt = select(sa.func.count()).select_from(CandidateJobMatch).where(*filters)
        stmt = (
            select(CandidateJobMatch)
            .where(*filters)
            .order_by(CandidateJobMatch.match_score.desc(), CandidateJobMatch.updated_at.desc())
        )
        pipeline_job_count = int(
            self.db.scalar(
                select(sa.func.count())
                .select_from(Pipeline)
                .where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.candidate_id == candidate_id,
                )
            )
            or 0
        )
        try:
            total_count = int(self.db.scalar(count_stmt) or 0)
            rows = list(self.db.scalars(stmt.offset(offset).limit(limit)))
        except ProgrammingError as exc:
            if "candidate_job_match" not in str(exc).lower():
                raise
            self.db.rollback()
            return CandidateMatchesResponse(
                candidate_id=candidate_id,
                matches=[],
                total_count=0,
                limit=limit,
                offset=offset,
                pipeline_job_count=pipeline_job_count,
                ats_hint="NO_SCORE_ROWS_YET" if pipeline_job_count > 0 else "NO_PIPELINE_JOBS",
            )
        matches: list[CandidateMatchEntry] = []
        for row in rows:
            cs = self._coerce_match_category_scores(row.category_scores)
            matches.append(
                CandidateMatchEntry(
                    job_id=row.job_id,
                    fit_score=row.match_score,
                    deterministic_match_score=getattr(row, "deterministic_match_score", None),
                    semantic_match_score=getattr(row, "semantic_match_score", None),
                    ai_enrichment_status=getattr(row, "ai_enrichment_status", None),
                    ats_pipeline_status=getattr(row, "ats_pipeline_status", None),
                    enrichment_started_at=getattr(row, "enrichment_started_at", None),
                    deterministic_completed_at=getattr(row, "deterministic_completed_at", None),
                    semantic_completed_at=getattr(row, "semantic_completed_at", None),
                    enrichment_error=getattr(row, "enrichment_error", None),
                    recruiter_summary=getattr(row, "recruiter_summary", None),
                    confidence_reasoning=getattr(row, "confidence_reasoning", None),
                    semantic_skill_matches=self._coerce_jsonb_str_list(
                        getattr(row, "semantic_skill_matches", None)
                    ),
                    transferable_skills=self._coerce_jsonb_str_list(getattr(row, "transferable_skills", None)),
                    inferred_strengths=self._coerce_jsonb_str_list(getattr(row, "inferred_strengths", None)),
                    inferred_gaps=self._coerce_jsonb_str_list(getattr(row, "inferred_gaps", None)),
                    category_scores=JobService._match_category_scores_model(cs),
                    matched_skills=self._coerce_jsonb_str_list(row.matched_skills),
                    missing_skills=self._coerce_jsonb_str_list(row.missing_skills),
                    recommendation=row.recommendation,
                    confidence_score=float(row.confidence_score or 0),
                    evaluated_at=getattr(row, "evaluated_at", None),
                )
            )
        ats_hint: str | None = None
        if total_count == 0:
            ats_hint = "NO_PIPELINE_JOBS" if pipeline_job_count == 0 else "NO_SCORE_ROWS_YET"

        return CandidateMatchesResponse(
            candidate_id=candidate_id,
            matches=matches,
            total_count=total_count,
            limit=limit,
            offset=offset,
            pipeline_job_count=pipeline_job_count,
            ats_hint=ats_hint,
        )

    def get_ats_pair_status(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
        job_id: UUID,
    ) -> AtsPairStatusResponse:
        row = self.db.scalar(
            select(CandidateJobMatch).where(
                CandidateJobMatch.organization_id == organization_id,
                CandidateJobMatch.candidate_id == candidate_id,
                CandidateJobMatch.job_id == job_id,
            )
        )
        if row is None:
            return AtsPairStatusResponse(
                candidate_id=candidate_id,
                job_id=job_id,
                processing_state=ATS_QUEUED,
                progress=5,
                last_updated=None,
                deterministic_score=None,
                semantic_score=None,
                final_score=None,
                semantic_completion_status="pending",
                enrichment_error=None,
            )
        state = getattr(row, "ats_pipeline_status", None) or ATS_PENDING
        progress_map = {
            ATS_QUEUED: 5,
            ATS_PENDING: 10,
            ATS_PARSING: 25,
            ATS_DETERMINISTIC_COMPLETE: 60,
            ATS_AI_ENRICHING: 80,
            ATS_COMPLETED: 100,
            ATS_FAILED: 100,
        }
        return AtsPairStatusResponse(
            candidate_id=candidate_id,
            job_id=job_id,
            processing_state=state,
            progress=progress_map.get(state, 0),
            last_updated=getattr(row, "updated_at", None),
            deterministic_score=getattr(row, "deterministic_match_score", None),
            semantic_score=getattr(row, "semantic_match_score", None),
            final_score=getattr(row, "match_score", None),
            semantic_completion_status=getattr(row, "ai_enrichment_status", None),
            enrichment_error=getattr(row, "enrichment_error", None),
            enqueue_delay_ms=None,
        )

    def rescore_job_sync(self, *, organization_id: UUID, job_id: UUID) -> int:
        return self.rescore_job_fast(organization_id=organization_id, job_id=job_id)

    def rescore_candidate_sync(self, *, organization_id: UUID, candidate_id: UUID) -> int:
        return self.rescore_candidate_fast(organization_id=organization_id, candidate_id=candidate_id)

    def rescore_job_fast(self, *, organization_id: UUID, job_id: UUID) -> int:
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        if job is None:
            return 0
        candidate_ids = list(
            self.db.scalars(
                select(Pipeline.candidate_id).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.job_id == job_id,
                )
            )
        )
        t_job = time.monotonic()
        for cid in candidate_ids:
            self.rescore_candidate_job_deterministic_sync(
                organization_id=organization_id, candidate_id=cid, job_id=job_id
            )
        self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
        for cid in candidate_ids:
            self.dispatch_enrich_candidate_job_semantic(
                organization_id=organization_id, candidate_id=cid, job_id=job_id
            )
        logger.info(
            "ats.rescore.job_fast_done",
            extra={
                "ats_phase": "rescore_job_fast",
                "organization_id": str(organization_id),
                "job_id": str(job_id),
                "pairs": len(candidate_ids),
                "duration_ms": int((time.monotonic() - t_job) * 1000),
            },
        )
        return len(candidate_ids)

    def rescore_candidate_fast(self, *, organization_id: UUID, candidate_id: UUID) -> int:
        job_ids = list(
            self.db.scalars(
                select(Pipeline.job_id).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.candidate_id == candidate_id,
                )
            )
        )
        t0 = time.monotonic()
        for job_id in job_ids:
            self.rescore_candidate_job_deterministic_sync(
                organization_id=organization_id, candidate_id=candidate_id, job_id=job_id
            )
            self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
            self.dispatch_enrich_candidate_job_semantic(
                organization_id=organization_id, candidate_id=candidate_id, job_id=job_id
            )
        logger.info(
            "ats.rescore.candidate_fast_done",
            extra={
                "ats_phase": "rescore_candidate_fast",
                "organization_id": str(organization_id),
                "candidate_id": str(candidate_id),
                "pairs": len(job_ids),
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        return len(job_ids)

    def rescore_candidate_full_sync(self, *, organization_id: UUID, candidate_id: UUID) -> int:
        """Synchronous full pipeline (deterministic + semantic) for every pipeline job."""
        job_ids = list(
            self.db.scalars(
                select(Pipeline.job_id).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.candidate_id == candidate_id,
                )
            )
        )
        for job_id in job_ids:
            self.rescore_candidate_job_full_sync(
                organization_id=organization_id, candidate_id=candidate_id, job_id=job_id
            )
            self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
        return len(job_ids)

    def rescore_job_full_sync(self, *, organization_id: UUID, job_id: UUID) -> int:
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        if job is None:
            return 0
        candidate_ids = list(
            self.db.scalars(
                select(Pipeline.candidate_id).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.job_id == job_id,
                )
            )
        )
        for cid in candidate_ids:
            self.rescore_candidate_job_full_sync(
                organization_id=organization_id, candidate_id=cid, job_id=job_id
            )
        self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
        return len(candidate_ids)

    @staticmethod
    def semantic_provider_configured() -> bool:
        s = get_settings()
        return bool((s.groq_ats_api_key or "").strip() or (s.grok_api_key or "").strip())

    def dispatch_enrich_candidate_job_semantic(
        self, *, organization_id: UUID, candidate_id: UUID, job_id: UUID
    ) -> None:
        if not self.semantic_provider_configured():
            return
        now = datetime.now(timezone.utc)
        row = self.db.scalar(
            select(CandidateJobMatch).where(
                CandidateJobMatch.organization_id == organization_id,
                CandidateJobMatch.candidate_id == candidate_id,
                CandidateJobMatch.job_id == job_id,
            )
        )
        if row is not None and row.ats_pipeline_status == ATS_AI_ENRICHING and row.enrichment_started_at is not None:
            age = (datetime.now(timezone.utc) - row.enrichment_started_at).total_seconds()
            if 0 < age < SEMANTIC_INFLIGHT_DEDUP_SECONDS:
                logger.info(
                    "ats.semantic.dispatch_skip_inflight",
                    extra={
                        "organization_id": str(organization_id),
                        "candidate_id": str(candidate_id),
                        "job_id": str(job_id),
                        "age_seconds": int(age),
                    },
                )
                return
        if row is not None and row.ats_pipeline_status not in (ATS_COMPLETED, ATS_AI_ENRICHING):
            row.ats_pipeline_status = ATS_QUEUED
            row.ai_enrichment_status = "pending"
            row.enrichment_started_at = now
            self.db.add(row)
        from app.candidate_management.tasks_ats import (
            enrich_candidate_job_semantic_task,
            run_enrich_candidate_job_semantic,
        )

        dispatch_task(
            task=enrich_candidate_job_semantic_task,
            fallback=run_enrich_candidate_job_semantic,
            kwargs={
                "organization_id": str(organization_id),
                "candidate_id": str(candidate_id),
                "job_id": str(job_id),
                "enqueued_at": now.isoformat(),
            },
        )

    def rescore_candidate_job_deterministic_sync(
        self, *, organization_id: UUID, candidate_id: UUID, job_id: UUID, force: bool = False
    ) -> None:
        """Persist baseline deterministic ATS quickly; semantic runs separately."""
        t0 = time.monotonic()
        extra_base = {
            "ats_phase": "rescore_candidate_job_deterministic",
            "organization_id": str(organization_id),
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
        }
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        if job is None:
            logger.warning(
                "ats.rescore.skip",
                extra={**extra_base, "reason": "job_not_found", "duration_ms": int((time.monotonic() - t0) * 1000)},
            )
            return
        candidate = self.db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                or_(
                    Candidate.organization_id == organization_id,
                    Candidate.org_id == organization_id,
                ),
            )
        )
        if candidate is None:
            logger.warning(
                "ats.rescore.skip",
                extra={
                    **extra_base,
                    "reason": "candidate_not_in_org",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            return

        logger.info("ats.rescore.started", extra={**extra_base, "mode": "deterministic_only"})

    def _refresh_job_match_cache(self, *, job_id: UUID, organization_id: UUID) -> None:
        try:
            early = self.db.scalar(
                select(CandidateJobMatch).where(
                    CandidateJobMatch.organization_id == organization_id,
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.job_id == job_id,
                )
            )
        except ProgrammingError as exc:
            # Backward compatibility: DB may not yet have lifecycle columns.
            if "column" in str(exc).lower() and "candidate_job_matches" in str(exc).lower():
                self.db.rollback()
                logger.warning(
                    "ats.rescore.lifecycle_columns_missing",
                    extra={**extra_base, "exception_class": type(exc).__name__},
                )
                early = None
            else:
                raise
        if not force:
            if early is not None and early.ats_pipeline_status == ATS_AI_ENRICHING and early.enrichment_started_at is not None:
                age = (datetime.now(timezone.utc) - early.enrichment_started_at).total_seconds()
                if 0 < age < SEMANTIC_INFLIGHT_DEDUP_SECONDS:
                    logger.info(
                        "ats.rescore.skip_pair_inflight_semantic",
                        extra={**extra_base, "age_seconds": int(age)},
                    )
                    return
        if early is not None:
            early.ats_pipeline_status = ATS_PARSING
            early.ai_enrichment_status = "pending"
            self.db.add(early)

        empty_resume_extra: dict[str, object] = {
            "skills": [],
            "titles": [],
            "years": None,
            "education": [],
            "certifications": [],
            "summary": None,
        }
        try:
            try:
                t_resume_extract = time.monotonic()
                extra = get_resume_extra_cached(
                    candidate.id,
                    loader=lambda: self._load_structured_resume_fields(candidate.id, organization_id),
                )
                logger.info(
                    "ats.timing.resume_extract",
                    extra={**extra_base, "duration_ms": int((time.monotonic() - t_resume_extract) * 1000)},
                )
            except Exception:
                logger.exception(
                    "ats.rescore.structured_fields_fallback",
                    extra={**extra_base},
                )
                extra = dict(empty_resume_extra)

            t_job_norm = time.monotonic()
            required_skills, preferred_skills = get_job_skills_cached(
                job.id,
                loader=lambda: (
                    list(
                        self.db.scalars(
                            select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(True))
                        )
                    ),
                    list(
                        self.db.scalars(
                            select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(False))
                        )
                    ),
                ),
            )
            logger.info(
                "ats.timing.job_normalize",
                extra={
                    **extra_base,
                    "duration_ms": int((time.monotonic() - t_job_norm) * 1000),
                    "required_skills_count": len(required_skills),
                    "preferred_skills_count": len(preferred_skills),
                },
            )
            candidate_blob = " ".join(
                [
                    (candidate.experience_summary or ""),
                    (candidate.education or ""),
                    (candidate.notes or ""),
                    (candidate.location or ""),
                ]
            ).lower()
            candidate_skill_hits: list[str] = []
            for skill in set(required_skills + preferred_skills):
                norm = self._jd_normalizer.normalize_skill(skill)
                if norm and norm in candidate_blob:
                    candidate_skill_hits.append(norm)
            years = self._extract_years_from_text(candidate.experience_summary)
            previous_titles = self._extract_titles_from_text(candidate.experience_summary or "")
            candidate_skills_for_scoring = list(
                dict.fromkeys(
                    [s for s in candidate_skill_hits if s]
                    + [s for s in extra.get("skills", []) if s]
                )
            )
            result = self._ats.score(
                candidate=CandidateScoringInput(
                    candidate_id=str(candidate.id),
                    skills=candidate_skills_for_scoring,
                    years_of_experience=years,
                    previous_titles=previous_titles,
                    education=[candidate.education] if candidate.education else [],
                    parser_confidence=0.6,
                ),
                job=JobScoringInput(
                    job_id=str(job.id),
                    title=job.title,
                    required_skills_normalized=required_skills,
                    preferred_skills_normalized=preferred_skills,
                    min_experience_years=float(job.experience_min_years)
                    if job.experience_min_years is not None
                    else None,
                    max_experience_years=float(job.experience_max_years)
                    if job.experience_max_years is not None
                    else None,
                    education_requirements=[],
                ),
            )
            det_score = result.match_score
            now = datetime.now(timezone.utc)
            category_scores = dict(result.category_scores or {})
            category_scores["hybrid"] = {
                "deterministic_score": det_score,
                "semantic_score": None,
                "final_score": det_score,
                "weights": {"deterministic": 1.0, "semantic": 0.0},
            }
            recommendation = ATSMatchingService._tier_for(det_score)
            semantic_on = self.semantic_provider_configured()
            if semantic_on:
                pipe_status = ATS_DETERMINISTIC_COMPLETE
                ai_status = "pending"
            else:
                pipe_status = ATS_COMPLETED
                ai_status = "skipped"

            t_persist = time.monotonic()
            try:
                row = self.db.scalar(
                    select(CandidateJobMatch).where(
                        CandidateJobMatch.organization_id == organization_id,
                        CandidateJobMatch.candidate_id == candidate.id,
                        CandidateJobMatch.job_id == job.id,
                    )
                )
                if row is None:
                    row = CandidateJobMatch(
                        organization_id=organization_id,
                        candidate_id=candidate.id,
                        job_id=job.id,
                        match_score=det_score,
                        deterministic_match_score=det_score,
                        semantic_match_score=None,
                        ai_enrichment_status=ai_status,
                        ats_pipeline_status=pipe_status,
                        category_scores=category_scores,
                        matched_skills=result.matched_skills,
                        missing_skills=result.missing_skills,
                        matched_preferred_skills=result.matched_preferred_skills,
                        recommendation=recommendation,
                        confidence_score=result.confidence_score,
                        evaluated_at=now,
                        deterministic_completed_at=now,
                        semantic_completed_at=now if not semantic_on else None,
                        enrichment_started_at=None,
                        enrichment_error=None,
                        recruiter_summary=None,
                        confidence_reasoning=None,
                        semantic_skill_matches=None,
                        transferable_skills=None,
                        inferred_strengths=None,
                        inferred_gaps=None,
                    )
                    self.db.add(row)
                else:
                    row.match_score = det_score
                    row.deterministic_match_score = det_score
                    row.semantic_match_score = None
                    row.ai_enrichment_status = ai_status
                    row.ats_pipeline_status = pipe_status
                    row.category_scores = category_scores
                    row.matched_skills = result.matched_skills
                    row.missing_skills = result.missing_skills
                    row.matched_preferred_skills = result.matched_preferred_skills
                    row.recommendation = recommendation
                    row.confidence_score = result.confidence_score
                    row.evaluated_at = now
                    row.deterministic_completed_at = now
                    row.semantic_completed_at = now if not semantic_on else None
                    row.enrichment_started_at = None
                    row.enrichment_error = None
                    row.recruiter_summary = None
                    row.confidence_reasoning = None
                    row.semantic_skill_matches = None
                    row.transferable_skills = None
                    row.inferred_strengths = None
                    row.inferred_gaps = None
                    self.db.add(row)

                det_ms = int((time.monotonic() - t0) * 1000)
                compute_ms = int((t_persist - t0) * 1000)
                db_ms = int((time.monotonic() - t_persist) * 1000)
                logger.info(
                    "ats.deterministic.completed",
                    extra={
                        **extra_base,
                        "deterministic_score": det_score,
                        "duration_ms": det_ms,
                        "deterministic_compute_ms": compute_ms,
                        "db_write_ms": db_ms,
                        "semantic_queued": semantic_on,
                    },
                )
            except ProgrammingError as exc:
                if "candidate_job_match" not in str(exc).lower():
                    raise
                logger.warning(
                    "ats.rescore.persist_skipped",
                    extra={
                        **extra_base,
                        "reason": "candidate_job_matches_table",
                        "exception_class": type(exc).__name__,
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    },
                )
                self.db.rollback()
                return
        except Exception as exc:
            logger.exception(
                "ats.rescore.failed",
                extra={
                    **extra_base,
                    "exception_class": type(exc).__name__,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            raise

    def enrich_candidate_job_semantic_sync(
        self, *, organization_id: UUID, candidate_id: UUID, job_id: UUID
    ) -> None:
        """Background semantic enrichment; updates hybrid score when successful."""
        if not self.semantic_provider_configured():
            return
        t0 = time.monotonic()
        extra_base = {
            "ats_phase": "enrich_candidate_job_semantic",
            "organization_id": str(organization_id),
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
        }
        logger.info("ats.semantic.started", extra={**extra_base, "context": "background_pair"})
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        candidate = self.db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                or_(
                    Candidate.organization_id == organization_id,
                    Candidate.org_id == organization_id,
                ),
            )
        )
        if job is None or candidate is None:
            logger.warning("ats.semantic.failed", extra={**extra_base, "reason": "missing_job_or_candidate"})
            return

        try:
            row = self.db.scalar(
                select(CandidateJobMatch)
                .where(
                    CandidateJobMatch.organization_id == organization_id,
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.job_id == job_id,
                )
                .with_for_update()
            )
        except ProgrammingError:
            self.db.rollback()
        try:
            row = self.db.scalar(
                select(CandidateJobMatch).where(
                    CandidateJobMatch.organization_id == organization_id,
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.job_id == job_id,
                )
            )
        except ProgrammingError as exc:
            if "column" in str(exc).lower() and "candidate_job_matches" in str(exc).lower():
                self.db.rollback()
                logger.warning(
                    "ats.semantic.dispatch_lifecycle_columns_missing",
                    extra={
                        "organization_id": str(organization_id),
                        "candidate_id": str(candidate_id),
                        "job_id": str(job_id),
                        "exception_class": type(exc).__name__,
                    },
                )
                return
            raise

        if row is None:
            logger.warning("ats.semantic.failed", extra={**extra_base, "reason": "no_match_row"})
            return

        if row.ats_pipeline_status == ATS_AI_ENRICHING and row.enrichment_started_at is not None:
            age = (datetime.now(timezone.utc) - row.enrichment_started_at).total_seconds()
            if 0 < age < SEMANTIC_INFLIGHT_DEDUP_SECONDS:
                logger.info(
                    "ats.semantic.skip_duplicate_inflight",
                    extra={**extra_base, "age_seconds": int(age)},
                )
                return

        now = datetime.now(timezone.utc)
        row.ats_pipeline_status = ATS_AI_ENRICHING
        row.ai_enrichment_status = "enriching"
        row.enrichment_started_at = now
        row.enrichment_error = None
        self.db.add(row)
        self.db.flush()

        empty_resume_extra: dict[str, object] = {
            "skills": [],
            "titles": [],
            "years": None,
            "education": [],
            "certifications": [],
            "summary": None,
        }
        ai_ms = 0
        try:
            try:
                t_resume_extract = time.monotonic()
                extra = get_resume_extra_cached(
                    candidate.id,
                    loader=lambda: self._load_structured_resume_fields(candidate.id, organization_id),
                )
                logger.info(
                    "ats.timing.resume_extract",
                    extra={**extra_base, "duration_ms": int((time.monotonic() - t_resume_extract) * 1000)},
                )
            except Exception:
                logger.exception("ats.rescore.structured_fields_fallback", extra={**extra_base})
                extra = dict(empty_resume_extra)

            t_job_norm = time.monotonic()
            required_skills, preferred_skills = get_job_skills_cached(
                job.id,
                loader=lambda: (
                    list(
                        self.db.scalars(
                            select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(True))
                        )
                    ),
                    list(
                        self.db.scalars(
                            select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(False))
                        )
                    ),
                ),
            )
            logger.info(
                "ats.timing.job_normalize",
                extra={
                    **extra_base,
                    "duration_ms": int((time.monotonic() - t_job_norm) * 1000),
                    "required_skills_count": len(required_skills),
                    "preferred_skills_count": len(preferred_skills),
                },
            )
            candidate_blob = " ".join(
                [
                    (candidate.experience_summary or ""),
                    (candidate.education or ""),
                    (candidate.notes or ""),
                    (candidate.location or ""),
                ]
            ).lower()
            candidate_skill_hits: list[str] = []
            for skill in set(required_skills + preferred_skills):
                norm = self._jd_normalizer.normalize_skill(skill)
                if norm and norm in candidate_blob:
                    candidate_skill_hits.append(norm)
            years = self._extract_years_from_text(candidate.experience_summary)
            previous_titles = self._extract_titles_from_text(candidate.experience_summary or "")
            candidate_skills_for_scoring = list(
                dict.fromkeys(
                    [s for s in candidate_skill_hits if s]
                    + [s for s in extra.get("skills", []) if s]
                )
            )
            result = self._ats.score(
                candidate=CandidateScoringInput(
                    candidate_id=str(candidate.id),
                    skills=candidate_skills_for_scoring,
                    years_of_experience=years,
                    previous_titles=previous_titles,
                    education=[candidate.education] if candidate.education else [],
                    parser_confidence=0.6,
                ),
                job=JobScoringInput(
                    job_id=str(job.id),
                    title=job.title,
                    required_skills_normalized=required_skills,
                    preferred_skills_normalized=preferred_skills,
                    min_experience_years=float(job.experience_min_years)
                    if job.experience_min_years is not None
                    else None,
                    max_experience_years=float(job.experience_max_years)
                    if job.experience_max_years is not None
                    else None,
                    education_requirements=[],
                ),
            )
            det_score = result.match_score
            merged_skills = candidate_skills_for_scoring
            merged_titles = list(
                dict.fromkeys(
                    [t for t in previous_titles if t]
                    + [t for t in extra.get("titles", []) if t]
                )
            )
            merged_years = years if years is not None else extra.get("years")
            merged_edu = ([candidate.education] if candidate.education else []) + list(extra.get("education", []))
            merged_edu = list(dict.fromkeys([e for e in merged_edu if e]))[:8]
            exp_summary = candidate.experience_summary or extra.get("summary") or ""
            job_summary_text = (job.description or "")[:1200] if job.description else None

            condensed = build_condensed_candidate_job_payload(
                candidate_skills=merged_skills,
                candidate_titles=merged_titles[:8],
                years_experience=float(merged_years) if merged_years is not None else None,
                education=merged_edu,
                certifications=list(extra.get("certifications", []))[:12],
                experience_summary=exp_summary,
                job_title=job.title,
                job_summary=job_summary_text,
                job_required_skills=required_skills,
                job_preferred_skills=preferred_skills,
                deterministic_score=det_score,
                deterministic_matched=list(result.matched_skills or []),
                deterministic_missing=list(result.missing_skills or []),
            )
            t_ai = time.monotonic()
            sem_svc = SemanticMatchingService()
            sem_result = sem_svc.enrich_pair(condensed)
            ai_ms = int((time.monotonic() - t_ai) * 1000)
            sem_int: int | None = sem_result.payload.semantic_match_score if sem_result else None
            final_score = hybrid_match_score(det_score, sem_int)
            logger.info(
                "ats.hybrid.final_score",
                extra={
                    **extra_base,
                    "deterministic_score": det_score,
                    "semantic_score": sem_int,
                    "final_score": final_score,
                    "ai_provider_latency_ms": ai_ms,
                },
            )
            recommendation = ATSMatchingService._tier_for(final_score)
            category_scores = dict(result.category_scores or {})
            category_scores["hybrid"] = {
                "deterministic_score": det_score,
                "semantic_score": sem_int,
                "final_score": final_score,
                "weights": {"deterministic": 0.7, "semantic": 0.3},
            }

            t_db0 = time.monotonic()
            if sem_result:
                row.match_score = final_score
                row.deterministic_match_score = det_score
                row.semantic_match_score = sem_int
                row.ai_enrichment_status = "complete"
                row.ats_pipeline_status = ATS_COMPLETED
                row.category_scores = category_scores
                row.matched_skills = result.matched_skills
                row.missing_skills = result.missing_skills
                row.matched_preferred_skills = result.matched_preferred_skills
                row.recommendation = recommendation
                row.confidence_score = result.confidence_score
                row.evaluated_at = datetime.now(timezone.utc)
                row.semantic_completed_at = datetime.now(timezone.utc)
                row.enrichment_error = None
                row.recruiter_summary = sem_result.payload.recruiter_summary
                row.confidence_reasoning = sem_result.payload.confidence_reasoning
                row.semantic_skill_matches = sem_result.payload.semantic_skill_matches
                row.transferable_skills = sem_result.payload.transferable_skills
                row.inferred_strengths = sem_result.payload.inferred_strengths
                row.inferred_gaps = sem_result.payload.inferred_gaps
            else:
                row.match_score = det_score
                row.deterministic_match_score = det_score
                row.semantic_match_score = None
                row.ai_enrichment_status = "failed"
                row.ats_pipeline_status = ATS_FAILED
                row.category_scores = category_scores
                row.enrichment_error = "Semantic enrichment returned no payload (provider error or parse failure)."
                row.semantic_completed_at = datetime.now(timezone.utc)

            self.db.add(row)
            self.db.flush()
            db_write_ms = int((time.monotonic() - t_db0) * 1000)
            logger.info(
                "ats.semantic.completed",
                extra={
                    **extra_base,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "ai_provider_latency_ms": ai_ms,
                    "db_write_ms": db_write_ms,
                    "final_score": row.match_score,
                },
            )
        except Exception as exc:
            logger.exception(
                "ats.semantic.failed",
                extra={
                    **extra_base,
                    "exception_class": type(exc).__name__,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "ai_provider_latency_ms": ai_ms,
                },
            )
            row.match_score = row.deterministic_match_score
            row.semantic_match_score = None
            row.ai_enrichment_status = "failed"
            row.ats_pipeline_status = ATS_FAILED
            row.enrichment_error = str(exc)[:2000]
            row.semantic_completed_at = datetime.now(timezone.utc)
            self.db.add(row)

    def rescore_candidate_job_full_sync(self, *, organization_id: UUID, candidate_id: UUID, job_id: UUID) -> None:
        t0 = time.monotonic()
        extra_base = {
            "ats_phase": "rescore_candidate_job_full_sync",
            "organization_id": str(organization_id),
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
        }
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        if job is None:
            logger.warning(
                "ats.rescore.skip",
                extra={**extra_base, "reason": "job_not_found", "duration_ms": int((time.monotonic() - t0) * 1000)},
            )
            return
        candidate = self.db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                or_(
                    Candidate.organization_id == organization_id,
                    Candidate.org_id == organization_id,
                ),
            )
        )
        if candidate is None:
            logger.warning(
                "ats.rescore.skip",
                extra={
                    **extra_base,
                    "reason": "candidate_not_in_org",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            return

        logger.info("ats.rescore.started", extra={**extra_base})

        empty_resume_extra: dict[str, object] = {
            "skills": [],
            "titles": [],
            "years": None,
            "education": [],
            "certifications": [],
            "summary": None,
        }
        try:
            try:
                extra = self._load_structured_resume_fields(candidate.id, organization_id)
            except Exception:
                logger.exception(
                    "ats.rescore.structured_fields_fallback",
                    extra={**extra_base},
                )
                extra = dict(empty_resume_extra)

            required_skills = list(
                self.db.scalars(
                    select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(True))
                )
            )
            preferred_skills = list(
                self.db.scalars(
                    select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(False))
                )
            )
            candidate_blob = " ".join(
                [
                    (candidate.experience_summary or ""),
                    (candidate.education or ""),
                    (candidate.notes or ""),
                    (candidate.location or ""),
                ]
            ).lower()
            candidate_skill_hits: list[str] = []
            for skill in set(required_skills + preferred_skills):
                norm = self._jd_normalizer.normalize_skill(skill)
                if norm and norm in candidate_blob:
                    candidate_skill_hits.append(norm)
            years = self._extract_years_from_text(candidate.experience_summary)
            previous_titles = self._extract_titles_from_text(candidate.experience_summary or "")
            # Build a richer skill set for deterministic scoring by combining
            # blob hits with structured extracted skills (when available).
            candidate_skills_for_scoring = list(
                dict.fromkeys(
                    [s for s in candidate_skill_hits if s]
                    + [s for s in extra.get("skills", []) if s]
                )
            )
            result = self._ats.score(
                candidate=CandidateScoringInput(
                    candidate_id=str(candidate.id),
                    skills=candidate_skills_for_scoring,
                    years_of_experience=years,
                    previous_titles=previous_titles,
                    education=[candidate.education] if candidate.education else [],
                    parser_confidence=0.6,
                ),
                job=JobScoringInput(
                    job_id=str(job.id),
                    title=job.title,
                    required_skills_normalized=required_skills,
                    preferred_skills_normalized=preferred_skills,
                    min_experience_years=float(job.experience_min_years)
                    if job.experience_min_years is not None
                    else None,
                    max_experience_years=float(job.experience_max_years)
                    if job.experience_max_years is not None
                    else None,
                    education_requirements=[],
                ),
            )
            det_score = result.match_score
            merged_skills = candidate_skills_for_scoring
            merged_titles = list(
                dict.fromkeys(
                    [t for t in previous_titles if t]
                    + [t for t in extra.get("titles", []) if t]
                )
            )
            merged_years = years if years is not None else extra.get("years")
            merged_edu = ([candidate.education] if candidate.education else []) + list(extra.get("education", []))
            merged_edu = list(dict.fromkeys([e for e in merged_edu if e]))[:8]
            exp_summary = candidate.experience_summary or extra.get("summary") or ""
            job_summary_text = (job.description or "")[:1200] if job.description else None

            condensed = build_condensed_candidate_job_payload(
                candidate_skills=merged_skills,
                candidate_titles=merged_titles[:8],
                years_experience=float(merged_years) if merged_years is not None else None,
                education=merged_edu,
                certifications=list(extra.get("certifications", []))[:12],
                experience_summary=exp_summary,
                job_title=job.title,
                job_summary=job_summary_text,
                job_required_skills=required_skills,
                job_preferred_skills=preferred_skills,
                deterministic_score=det_score,
                deterministic_matched=list(result.matched_skills or []),
                deterministic_missing=list(result.missing_skills or []),
            )
            sem_svc = SemanticMatchingService()
            sem_result = sem_svc.enrich_pair(condensed)
            sem_int: int | None = sem_result.payload.semantic_match_score if sem_result else None
            final_score = hybrid_match_score(det_score, sem_int)
            logger.info(
                "ats.hybrid.final_score",
                extra={
                    **extra_base,
                    "deterministic_score": det_score,
                    "semantic_score": sem_int,
                    "final_score": final_score,
                },
            )
            recommendation = ATSMatchingService._tier_for(final_score)
            category_scores = dict(result.category_scores or {})
            category_scores["hybrid"] = {
                "deterministic_score": det_score,
                "semantic_score": sem_int,
                "final_score": final_score,
                "weights": {"deterministic": 0.7, "semantic": 0.3},
            }

            settings = get_settings()
            semantic_configured = bool((settings.groq_ats_api_key or "").strip() or (settings.grok_api_key or "").strip())
            if sem_result:
                ai_status = "complete"
            elif not semantic_configured:
                ai_status = "skipped"
            else:
                ai_status = "failed"

            logger.info(
                "ats.rescore.semantic_enrichment",
                extra={
                    **extra_base,
                    "semantic_score": sem_int,
                    "ai_enrichment_status": ai_status,
                    "grok_configured": bool((settings.grok_api_key or "").strip()),
                },
            )

            finalize_ts = datetime.now(timezone.utc)
            if sem_result:
                pipe_final = ATS_COMPLETED
                enrich_err = None
            elif not semantic_configured:
                pipe_final = ATS_COMPLETED
                enrich_err = None
            else:
                pipe_final = ATS_FAILED
                enrich_err = "Semantic enrichment returned no payload (provider error or parse failure)."

            try:
                row = self.db.scalar(
                    select(CandidateJobMatch).where(
                        CandidateJobMatch.organization_id == organization_id,
                        CandidateJobMatch.candidate_id == candidate.id,
                        CandidateJobMatch.job_id == job.id,
                    )
                )
                if row is None:
                    row = CandidateJobMatch(
                        organization_id=organization_id,
                        candidate_id=candidate.id,
                        job_id=job.id,
                        match_score=final_score,
                        deterministic_match_score=det_score,
                        semantic_match_score=sem_int,
                        ai_enrichment_status=ai_status,
                        ats_pipeline_status=pipe_final,
                        category_scores=category_scores,
                        matched_skills=result.matched_skills,
                        missing_skills=result.missing_skills,
                        matched_preferred_skills=result.matched_preferred_skills,
                        recommendation=recommendation,
                        confidence_score=result.confidence_score,
                        evaluated_at=finalize_ts,
                        deterministic_completed_at=finalize_ts,
                        semantic_completed_at=finalize_ts,
                        enrichment_started_at=None,
                        enrichment_error=enrich_err,
                        recruiter_summary=sem_result.payload.recruiter_summary if sem_result else None,
                        confidence_reasoning=sem_result.payload.confidence_reasoning if sem_result else None,
                        semantic_skill_matches=sem_result.payload.semantic_skill_matches if sem_result else None,
                        transferable_skills=sem_result.payload.transferable_skills if sem_result else None,
                        inferred_strengths=sem_result.payload.inferred_strengths if sem_result else None,
                        inferred_gaps=sem_result.payload.inferred_gaps if sem_result else None,
                    )
                    self.db.add(row)
                else:
                    row.match_score = final_score
                    row.deterministic_match_score = det_score
                    row.semantic_match_score = sem_int
                    row.ai_enrichment_status = ai_status
                    row.ats_pipeline_status = pipe_final
                    row.category_scores = category_scores
                    row.matched_skills = result.matched_skills
                    row.missing_skills = result.missing_skills
                    row.matched_preferred_skills = result.matched_preferred_skills
                    row.recommendation = recommendation
                    row.confidence_score = result.confidence_score
                    row.evaluated_at = finalize_ts
                    row.deterministic_completed_at = finalize_ts
                    row.semantic_completed_at = finalize_ts
                    row.enrichment_started_at = None
                    row.enrichment_error = enrich_err
                    if sem_result:
                        row.recruiter_summary = sem_result.payload.recruiter_summary
                        row.confidence_reasoning = sem_result.payload.confidence_reasoning
                        row.semantic_skill_matches = sem_result.payload.semantic_skill_matches
                        row.transferable_skills = sem_result.payload.transferable_skills
                        row.inferred_strengths = sem_result.payload.inferred_strengths
                        row.inferred_gaps = sem_result.payload.inferred_gaps
                    else:
                        row.recruiter_summary = None
                        row.confidence_reasoning = None
                        row.semantic_skill_matches = None
                        row.transferable_skills = None
                        row.inferred_strengths = None
                        row.inferred_gaps = None
                    self.db.add(row)
                logger.info(
                    "ats.rescore.completed",
                    extra={
                        **extra_base,
                        "deterministic_score": det_score,
                        "final_score": final_score,
                        "ai_enrichment_status": ai_status,
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    },
                )
            except ProgrammingError as exc:
                if "candidate_job_match" not in str(exc).lower():
                    raise
                logger.warning(
                    "ats.rescore.persist_skipped",
                    extra={
                        **extra_base,
                        "reason": "candidate_job_matches_table",
                        "exception_class": type(exc).__name__,
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    },
                )
                self.db.rollback()
                return
        except Exception as exc:
            logger.exception(
                "ats.rescore.failed",
                extra={
                    **extra_base,
                    "exception_class": type(exc).__name__,
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                },
            )
            raise

    def dispatch_rescore_job(self, *, organization_id: UUID, job_id: UUID) -> None:
        from app.candidate_management.tasks_ats import rescore_job_task, run_rescore_job

        dispatch_task(
            task=rescore_job_task,
            fallback=run_rescore_job,
            kwargs={"organization_id": str(organization_id), "job_id": str(job_id)},
        )

    def dispatch_rescore_candidate(self, *, organization_id: UUID, candidate_id: UUID) -> None:
        from app.candidate_management.tasks_ats import rescore_candidate_task, run_rescore_candidate

        dispatch_task(
            task=rescore_candidate_task,
            fallback=run_rescore_candidate,
            kwargs={"organization_id": str(organization_id), "candidate_id": str(candidate_id)},
        )

    def _refresh_job_match_cache(self, *, job_id: UUID, organization_id: UUID) -> None:
        try:
            rows = list(
                self.db.scalars(
                    select(CandidateJobMatch)
                    .where(
                        CandidateJobMatch.organization_id == organization_id,
                        CandidateJobMatch.job_id == job_id,
                    )
                    .order_by(CandidateJobMatch.match_score.desc(), CandidateJobMatch.updated_at.desc())
                    .limit(100)
                )
            )
        except ProgrammingError as exc:
            if "candidate_job_match" not in str(exc).lower():
                raise
            self.db.rollback()
            return
        ranked = [
            {
                "candidate_id": str(row.candidate_id),
                "fit_score": int(row.match_score),
                "category_scores": self._coerce_match_category_scores(row.category_scores),
            }
            for row in rows
        ]
        # `job_match_cache` is an optional optimization; if the table doesn't exist yet
        # we still want `candidate_job_matches` to persist (so the ATS UI can render).
        if not self._job_match_cache_table_exists():
            return

        cached = self.db.scalar(select(JobMatchCache).where(JobMatchCache.job_id == job_id))
        if cached is None:
            cached = JobMatchCache(job_id=job_id, ranked_candidate_ids=ranked)
        else:
            cached.ranked_candidate_ids = ranked
        self.db.add(cached)

    def _job_match_cache_table_exists(self) -> bool:
        settings = get_settings()
        schema = settings.db_schema
        table_fqn = f"{schema}.job_match_cache" if schema else "job_match_cache"
        # `to_regclass` returns NULL when the relation doesn't exist.
        exists = self.db.scalar(sa.text("select to_regclass(:t) is not null"), {"t": table_fqn})
        return bool(exists)

    def _load_structured_resume_fields(self, candidate_id: UUID, organization_id: UUID) -> dict[str, object]:
        """Best-effort JSON resume fields from unified `candidates` row (org_id / organization_id)."""
        t0 = time.monotonic()
        empty: dict[str, object] = {
            "skills": [],
            "titles": [],
            "years": None,
            "education": [],
            "certifications": [],
            "summary": None,
        }
        try:
            row = self.db.execute(
                text(
                    """
                    SELECT parsed_resume_data, summary, headline, years_experience
                    FROM candidates
                    WHERE id = :cid
                      AND (
                        organization_id = :oid
                        OR org_id = :oid
                      )
                    LIMIT 1
                    """
                ),
                {"cid": candidate_id, "oid": organization_id},
            ).mappings().first()
        except ProgrammingError:
            self.db.rollback()
            logger.warning("structured_resume_fields_query_failed candidate=%s", candidate_id)
            return empty
        except Exception:
            logger.exception("structured_resume_fields_unexpected candidate=%s", candidate_id)
            self.db.rollback()
            return empty

        if not row:
            logger.info(
                "ats.resume.extract.completed",
                extra={
                    "ats_phase": "resume_extract",
                    "candidate_id": str(candidate_id),
                    "organization_id": str(organization_id),
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "status": "empty",
                },
            )
            return empty

        parsed = row.get("parsed_resume_data")
        skills: list[str] = []
        titles: list[str] = []
        education: list[str] = []
        certs: list[str] = []
        if isinstance(parsed, dict):
            for key in ("skills", "normalized_keywords", "inferred_skills"):
                raw = parsed.get(key)
                if isinstance(raw, list):
                    skills.extend(str(x).strip().lower() for x in raw if x)
            pt = parsed.get("previous_titles")
            if isinstance(pt, list):
                titles.extend(str(x).strip() for x in pt if x)
            edu = parsed.get("education")
            if isinstance(edu, str) and edu.strip():
                education.append(edu.strip())
            elif isinstance(edu, list):
                education.extend(str(x).strip() for x in edu if x)
            c = parsed.get("certifications")
            if isinstance(c, list):
                certs.extend(str(x).strip() for x in c if x)

        y = row.get("years_experience")
        years_val: int | float | None = None
        if y is not None:
            try:
                years_val = float(y)
            except (TypeError, ValueError):
                years_val = None

        summary_parts = [row.get("summary"), row.get("headline")]
        summary = " ".join(str(p).strip() for p in summary_parts if p).strip() or None

        result = {
            "skills": list(dict.fromkeys(skills))[:50],
            "titles": titles[:8],
            "years": years_val,
            "education": education[:8],
            "certifications": certs[:12],
            "summary": summary,
        }
        logger.info(
            "ats.resume.extract.completed",
            extra={
                "ats_phase": "resume_extract",
                "candidate_id": str(candidate_id),
                "organization_id": str(organization_id),
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "skills_count": len(result["skills"]),
                "titles_count": len(result["titles"]),
            },
        )
        return result

    @staticmethod
    def _extract_years_from_text(text: str | None) -> float | None:
        if not text:
            return None
        import re

        m = re.search(r"(\\d+(?:\\.\\d+)?)\\s*\\+?\\s*(?:years?|yrs?)", text, flags=re.IGNORECASE)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_titles_from_text(text: str) -> list[str]:
        if not text:
            return []
        parts = [p.strip() for p in text.split(",") if p.strip()]
        return parts[:5]

    # -------------------------------
    # Internal helpers
    # -------------------------------
    @staticmethod
    def _match_category_scores_model(cs: dict[str, object]) -> JobMatchCategoryScores:
        """Map JSONB category_scores to API model, including optional hybrid sub-object."""
        hybrid: HybridScoreBreakdown | None = None
        raw_h = cs.get("hybrid")
        if isinstance(raw_h, dict):
            try:
                hybrid = HybridScoreBreakdown.model_validate(raw_h)
            except Exception:  # noqa: BLE001 — invalid legacy blobs must not 500 list endpoints
                hybrid = None
        return JobMatchCategoryScores(
            required_skills=int(cs.get("required_skills") or 0),
            preferred_skills=int(cs.get("preferred_skills") or 0),
            experience=int(cs.get("experience") or 0),
            title=int(cs.get("title") or 0),
            education=int(cs.get("education") or 0),
            hybrid=hybrid,
        )

    @staticmethod
    def _coerce_match_category_scores(raw: object) -> dict[str, object]:
        """JSONB may contain non-dicts from legacy or manual edits; avoid 500s on read."""
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _coerce_jsonb_str_list(raw: object) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        return []

    def _scalar_job_match_cache(self, job_id: UUID) -> JobMatchCache | None:
        """Load legacy cache row; tolerate DBs that never created `job_match_cache`."""
        try:
            return self.db.scalar(select(JobMatchCache).where(JobMatchCache.job_id == job_id))
        except ProgrammingError as exc:
            if "job_match_cache" not in str(exc).lower():
                raise
            self.db.rollback()
            return None

    def _upsert_job_skills(
        self,
        *,
        job_id: UUID,
        required_skills: list[str] | None,
        preferred_skills: list[str] | None,
    ) -> bool:
        """Replace skills for a job using normalized values.

        Returns True on success and False if the upsert failed (caller can use
        this to set `parsing_status='failed'`). We persist canonical skill
        names (lowercased + alias-mapped) so the matching engine and the JD
        normalizer always agree on what a skill is.
        """
        try:
            normalized = self._jd_normalizer.normalize(
                required_skills=required_skills,
                preferred_skills=preferred_skills,
            )

            self.db.execute(sa.delete(JobSkill).where(JobSkill.job_id == job_id))
            for skill in normalized.required_skills_normalized:
                self.db.add(JobSkill(job_id=job_id, skill=skill, is_required=True))
            for skill in normalized.preferred_skills_normalized:
                self.db.add(JobSkill(job_id=job_id, skill=skill, is_required=False))
            self.db.flush()
            return True
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"SKILL_UPSERT_FAILED: {e}")
            # Do NOT rollback the whole session here, as it would undo the main job update.
            return False
