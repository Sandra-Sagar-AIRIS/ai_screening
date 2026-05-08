from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
import sqlalchemy as sa
from sqlalchemy import Select, select
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
    CandidateMatchEntry,
    CandidateMatchesResponse,
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
from app.core.config import get_settings


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
            except Exception:
                self.db.rollback()
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

    def get_matches(
        self,
        *,
        job_id: UUID,
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
                    Candidate.organization_id == organization_id,
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
                    category_scores=JobMatchCategoryScores(
                        required_skills=int(cs.get("required_skills") or 0),
                        preferred_skills=int(cs.get("preferred_skills") or 0),
                        experience=int(cs.get("experience") or 0),
                        title=int(cs.get("title") or 0),
                        education=int(cs.get("education") or 0),
                    ),
                    already_submitted=row.candidate_id in submitted_ids,
                    matched_skills=self._coerce_jsonb_str_list(row.matched_skills),
                    missing_skills=self._coerce_jsonb_str_list(row.missing_skills),
                    recommendation=row.recommendation,
                    confidence_score=float(row.confidence_score or 0),
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
            )
        matches: list[CandidateMatchEntry] = []
        for row in rows:
            cs = self._coerce_match_category_scores(row.category_scores)
            matches.append(
                CandidateMatchEntry(
                    job_id=row.job_id,
                    fit_score=row.match_score,
                    category_scores=JobMatchCategoryScores(
                        required_skills=int(cs.get("required_skills") or 0),
                        preferred_skills=int(cs.get("preferred_skills") or 0),
                        experience=int(cs.get("experience") or 0),
                        title=int(cs.get("title") or 0),
                        education=int(cs.get("education") or 0),
                    ),
                    matched_skills=self._coerce_jsonb_str_list(row.matched_skills),
                    missing_skills=self._coerce_jsonb_str_list(row.missing_skills),
                    recommendation=row.recommendation,
                    confidence_score=float(row.confidence_score or 0),
                )
            )
        return CandidateMatchesResponse(
            candidate_id=candidate_id,
            matches=matches,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def rescore_job_sync(self, *, organization_id: UUID, job_id: UUID) -> int:
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
        count = 0
        for cid in candidate_ids:
            self.rescore_candidate_job_sync(organization_id=organization_id, candidate_id=cid, job_id=job_id)
            count += 1
        self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
        return count

    def rescore_candidate_sync(self, *, organization_id: UUID, candidate_id: UUID) -> int:
        job_ids = list(
            self.db.scalars(
                select(Pipeline.job_id).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.candidate_id == candidate_id,
                )
            )
        )
        count = 0
        for job_id in job_ids:
            self.rescore_candidate_job_sync(organization_id=organization_id, candidate_id=candidate_id, job_id=job_id)
            self._refresh_job_match_cache(job_id=job_id, organization_id=organization_id)
            count += 1
        return count

    def rescore_candidate_job_sync(self, *, organization_id: UUID, candidate_id: UUID, job_id: UUID) -> None:
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        candidate = self.db.scalar(
            select(Candidate).where(Candidate.id == candidate_id, Candidate.organization_id == organization_id)
        )
        if job is None or candidate is None:
            return
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
        result = self._ats.score(
            candidate=CandidateScoringInput(
                candidate_id=str(candidate.id),
                skills=candidate_skill_hits,
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
                min_experience_years=float(job.experience_min_years) if job.experience_min_years is not None else None,
                max_experience_years=float(job.experience_max_years) if job.experience_max_years is not None else None,
                education_requirements=[],
            ),
        )
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
                    match_score=result.match_score,
                    category_scores=result.category_scores,
                    matched_skills=result.matched_skills,
                    missing_skills=result.missing_skills,
                    matched_preferred_skills=result.matched_preferred_skills,
                    recommendation=result.recommendation,
                    confidence_score=result.confidence_score,
                    evaluated_at=datetime.now(timezone.utc),
                )
                self.db.add(row)
            else:
                row.match_score = result.match_score
                row.category_scores = result.category_scores
                row.matched_skills = result.matched_skills
                row.missing_skills = result.missing_skills
                row.matched_preferred_skills = result.matched_preferred_skills
                row.recommendation = result.recommendation
                row.confidence_score = result.confidence_score
                row.evaluated_at = datetime.now(timezone.utc)
                self.db.add(row)
        except ProgrammingError as exc:
            if "candidate_job_match" not in str(exc).lower():
                raise
            self.db.rollback()
            return

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
