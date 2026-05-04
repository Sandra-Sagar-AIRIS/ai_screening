from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_skill import JobSkill
from app.models.job_match_cache import JobMatchCache
from app.models.job_submission import JobSubmission
from app.schemas.auth import CurrentUser
from app.schemas.job import (
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


DEV_MODE = True

class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._clients = ClientService(db)
        self._scope = AccessScopeService(db)
        self._candidates = CandidateService(db)
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
            status=payload.status.value,
            location=payload.location,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            salary_currency=payload.salary_currency,
            experience_min_years=payload.experience_min_years,
            experience_max_years=payload.experience_max_years,
            employment_type=payload.employment_type,
            urgency=payload.urgency,
            raw_jd_text=payload.raw_jd_text,
            parsing_source=payload.parsing_source,
            parsing_status=payload.parsing_status,
            created_by=created_by,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # Store job skills (Phase 1).
        if payload.required_skills or payload.preferred_skills:
            self._upsert_job_skills(
                job_id=job.id,
                required_skills=payload.required_skills,
                preferred_skills=payload.preferred_skills,
            )
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
        if client_id is not None:
            stmt = stmt.where(Job.client_id == client_id)
        allowed_job_ids = self._scope.allowed_job_ids(current_user)
        if self._scope.is_client_user(current_user):
            if not allowed_job_ids:
                return []
            stmt = stmt.where(Job.id.in_(allowed_job_ids))
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        jobs = list(self.db.scalars(stmt))
        return [self._get_job_response(job) for job in jobs]

    def get_job_by_id(self, job_id: UUID, organization_id: UUID, current_user: CurrentUser | None = None) -> Job:
        stmt: Select[tuple[Job]] = select(Job).where(
            Job.id == job_id,
            Job.organization_id == organization_id,
        )
        if current_user is not None and self._scope.is_client_user(current_user):
            allowed_job_ids = self._scope.allowed_job_ids(current_user)
            stmt = stmt.where(Job.id.in_(allowed_job_ids))
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
            update_data["status"] = update_data["status"].value

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
        if "required_skills" in update_data or "preferred_skills" in update_data:
            required_skills = update_data.pop("required_skills", None)
            preferred_skills = update_data.pop("preferred_skills", None)
            self._upsert_job_skills(
                job_id=job.id,
                required_skills=required_skills,
                preferred_skills=preferred_skills,
            )

        for field, value in update_data.items():
            setattr(job, field, value)

        try:
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
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

    def change_job_status(
        self,
        *,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        new_status: JobStatus,
    ) -> JobResponse:
        job = self.get_job_by_id(job_id, organization_id, current_user)

        current_status = job.status
        target_status = new_status.value

        # Treat legacy "closed" as cancelled terminal state.
        cancelled_values = {JobStatus.CANCELLED.value, JobStatus.CLOSED.value}
        on_hold_value = JobStatus.ON_HOLD.value
        open_value = JobStatus.OPEN.value
        draft_value = JobStatus.DRAFT.value
        filled_value = JobStatus.FILLED.value

        def _normalize(status_value: str) -> str:
            if status_value in cancelled_values:
                return JobStatus.CANCELLED.value
            return status_value

        current_status = _normalize(current_status)
        target_status = _normalize(target_status)

        allowed: dict[str, set[str]] = {
            draft_value: {open_value, JobStatus.CANCELLED.value, filled_value},
            open_value: {on_hold_value, filled_value, JobStatus.CANCELLED.value, draft_value},
            on_hold_value: {open_value, filled_value, JobStatus.CANCELLED.value, draft_value},
            filled_value: {open_value, JobStatus.CANCELLED.value, on_hold_value, draft_value},
            JobStatus.CANCELLED.value: {open_value, filled_value, on_hold_value, draft_value},
        }

        if target_status not in allowed.get(current_status, set()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_STATUS_TRANSITION")

        if target_status == filled_value:
            job.filled_at = datetime.now(timezone.utc)

        job.status = target_status
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return self._get_job_response(job)

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

        # Phase 1 spec: accept only "open" or "on_hold".
        if job.status not in {JobStatus.OPEN.value, JobStatus.ON_HOLD.value}:
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
            self.db.commit()
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

        self.db.refresh(submission)

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
        )

        try:
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
        # Phase 1: compute synchronously and store in `job_match_cache`.
        # (The spec calls for async + ai-services, but this repo currently does not integrate it.)
        refresh = request.refresh

        job = self.get_job_by_id(job_id, organization_id, current_user)

        try:
            cached = self.db.scalar(select(JobMatchCache).where(JobMatchCache.job_id == job.id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch matches (migration missing?): {e}")
            self.db.rollback()
            cached = None

        if cached is not None and not refresh and cached.ranked_candidate_ids:
            return JobMatchTriggerResponse(
                job_id=job.id,
                match_count=len(cached.ranked_candidate_ids or []),
                generated_at=cached.generated_at,
                refresh_requested=False,
            )

        try:
            required_skills = self.db.scalars(
                select(JobSkill.skill).where(JobSkill.job_id == job.id, JobSkill.is_required.is_(True))
            ).all()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch job skills (migration missing?): {e}")
            self.db.rollback()
            required_skills = []

        required_normalized = [s.strip().lower() for s in required_skills if s and s.strip()]

        # Fetch candidates using legacy candidate service (availability across schema versions).
        # Note: Candidate schema differs in the new candidate-management module; this keeps Phase 1 working.
        candidates: list = []
        # Legacy CandidateService.list_candidates is limited to 50; page through a bit.
        page_limit = 50
        offset = 0
        while True:
            page = self._candidates.list_candidates(
                organization_id=organization_id,
                current_user=current_user,
                limit=page_limit,
                offset=offset,
            )
            if not page:
                break
            candidates.extend(page)
            if len(page) < page_limit:
                break
            offset += page_limit
            if len(candidates) >= 200:
                break

        ranked: list[dict[str, object]] = []
        for idx, candidate in enumerate(candidates):
            candidate_loc = (getattr(candidate, "location", None) or "").lower()
            candidate_exp = (getattr(candidate, "experience_summary", None) or "").lower()
            candidate_notes = (getattr(candidate, "notes", None) or "").lower()
            blob = f"{candidate_loc} {candidate_exp} {candidate_notes}"

            overlap = 0
            for skill in required_normalized:
                if skill and skill in blob:
                    overlap += 1

            num_required = max(1, len(required_normalized))
            skills_overlap_score = int(round(100 * overlap / num_required))

            location_score = 100 if job.location and job.location.lower() in candidate_loc else 70

            # Task 5: Improve experience matching logic
            cand_years_exp = getattr(candidate, "years_experience", None)
            experience_fit = 60 # Default if unknown

            if job.experience_min_years is None and job.experience_max_years is None:
                experience_fit = 70 # Neutral/Unknown job requirements
            elif cand_years_exp is not None:
                min_exp = job.experience_min_years or 0
                max_exp = job.experience_max_years or float('inf')

                if min_exp <= cand_years_exp <= max_exp:
                    experience_fit = 100
                elif cand_years_exp < min_exp:
                    gap = min_exp - cand_years_exp
                    experience_fit = max(0, 100 - (gap * 15)) # -15 per year gap
                else: # overqualified
                    experience_fit = 90

            # Compute fit_score with potential salary boost
            fit_score = int(
                round(0.6 * skills_overlap_score + 0.25 * location_score + 0.15 * experience_fit)
            )

            # Optional salary boost (if candidate has expected_salary)
            cand_expected_salary = getattr(candidate, "expected_salary", None)
            if cand_expected_salary is not None and job.salary_min is not None and job.salary_max is not None:
                 if job.salary_min <= cand_expected_salary <= job.salary_max:
                     fit_score = min(100, fit_score + 5) # 5 point boost

            ranked.append(
                {
                    "candidate_id": str(candidate.id),
                    "fit_score": fit_score,
                    "category_scores": {
                        "skills_overlap": skills_overlap_score,
                        "location_compatibility": location_score,
                        "experience_fit": experience_fit,
                    },
                }
            )

        ranked.sort(key=lambda x: int(x.get("fit_score") or 0), reverse=True)
        # Store only top N to keep JSON small.
        top_n = 100
        ranked = ranked[:top_n]

        from datetime import datetime, timezone
        generated_time = datetime.now(timezone.utc)

        try:
            if cached is None:
                cached = JobMatchCache(job_id=job.id, ranked_candidate_ids=ranked)
                self.db.add(cached)
                self.db.commit()
                self.db.refresh(cached)
                generated_time = cached.generated_at
            else:
                cached.ranked_candidate_ids = ranked
                self.db.add(cached)
                self.db.commit()
                self.db.refresh(cached)
                generated_time = cached.generated_at
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not save job match cache (migration missing?): {e}")
            self.db.rollback()

        return JobMatchTriggerResponse(
            job_id=job.id,
            match_count=len(ranked),
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
    ) -> JobMatchesResponse:
        job = self.get_job_by_id(job_id, organization_id, current_user)

        try:
            cached = self.db.scalar(select(JobMatchCache).where(JobMatchCache.job_id == job.id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch matches (migration missing?): {e}")
            self.db.rollback()
            return JobMatchesResponse(job_id=job.id, matches=[], total_count=0, generated_at=job.created_at, limit=limit, offset=offset)

        if cached is None or not cached.ranked_candidate_ids:
            return JobMatchesResponse(job_id=job.id, matches=[], total_count=0, generated_at=job.created_at, limit=limit, offset=offset)

        matches_raw = cached.ranked_candidate_ids or []

        # Apply pagination at the response layer.
        sliced = matches_raw[offset : offset + limit]

        candidate_ids_for_page: list[UUID] = []
        for raw_ranked in sliced:
            try:
                candidate_ids_for_page.append(UUID(str(raw_ranked.get("candidate_id"))))
            except Exception:  # pragma: no cover
                continue

        try:
            submitted_ids = set(
                self.db.scalars(
                    select(JobSubmission.candidate_id).where(
                        JobSubmission.job_id == job.id,
                        JobSubmission.candidate_id.in_(candidate_ids_for_page),
                    )
                )
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not fetch match submissions (migration missing?): {e}")
            self.db.rollback()
            submitted_ids = set()

        matches: list[JobMatchEntry] = []
        for raw_ranked in sliced:
            candidate_id = UUID(str(raw_ranked.get("candidate_id")))
            fit_score = int(raw_ranked.get("fit_score") or 0)
            category_scores_raw = raw_ranked.get("category_scores") or {}
            category_scores = JobMatchCategoryScores(
                skills_overlap=int(category_scores_raw.get("skills_overlap") or 0),
                location_compatibility=int(category_scores_raw.get("location_compatibility") or 0),
                experience_fit=int(category_scores_raw.get("experience_fit") or 0),
            )
            matches.append(
                JobMatchEntry(
                    rank=len(matches) + 1 + offset,
                    candidate_id=candidate_id,
                    fit_score=fit_score,
                    category_scores=category_scores,
                    already_submitted=candidate_id in submitted_ids,
                )
            )

        return JobMatchesResponse(
            job_id=job.id,
            matches=matches,
            total_count=len(matches_raw),
            generated_at=cached.generated_at,
            limit=limit,
            offset=offset,
        )

    # -------------------------------
    # Internal helpers
    # -------------------------------
    def _upsert_job_skills(
        self,
        *,
        job_id: UUID,
        required_skills: list[str] | None,
        preferred_skills: list[str] | None,
    ) -> None:
        try:
            # Replace strategy: delete existing rows for the job, then re-insert.
            self.db.execute(sa.delete(JobSkill).where(JobSkill.job_id == job_id))

            normalized_required = [s.strip() for s in (required_skills or []) if s and s.strip()]
            normalized_preferred = [s.strip() for s in (preferred_skills or []) if s and s.strip()]

            # Dedupe case-insensitively, keep required over preferred.
            required_set = {s.lower() for s in normalized_required}
            preferred_set = {s.lower() for s in normalized_preferred}

            to_create: list[JobSkill] = []

            required_seen_lower: set[str] = set()
            for raw in normalized_required:
                lower = raw.lower()
                if lower in required_set and lower not in required_seen_lower:
                    required_seen_lower.add(lower)
                    to_create.append(JobSkill(job_id=job_id, skill=raw, is_required=True))

            preferred_seen_lower: set[str] = set()
            for raw in normalized_preferred:
                lower = raw.lower()
                if lower in preferred_set and lower not in required_set and lower not in preferred_seen_lower:
                    preferred_seen_lower.add(lower)
                    to_create.append(JobSkill(job_id=job_id, skill=raw, is_required=False))

            for skill in to_create:
                self.db.add(skill)
                
            self.db.flush()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"SKILL_UPSERT_FAILED: {e}")
            # Do NOT rollback the whole session here, as it would undo the main job update.
            # Instead, we just fail to update skills.
