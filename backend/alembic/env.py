from __future__ import annotations

import os
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.utils.redaction import redact_database_url

# Import every model module so its tables register on Base.metadata before
# target_metadata is captured below. AIRIS is schema-per-service (see
# alembic/versions/0001_initial.py) — autogenerate correctness depends on
# every service's models being present here, not just a subset.
from app.models.ai_screening import (  # noqa: F401
    AIScreening,
    AIScreeningAnswer,
    AIScreeningEvaluation,
    AIScreeningMessage,
    AIScreeningQuestion,
)
from app.models.ai_screening_segment import AIScreeningSegment  # noqa: F401
from app.models.application import Application  # noqa: F401
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.candidate import Candidate  # noqa: F401
from app.models.candidate_job_match import CandidateJobMatch  # noqa: F401
from app.models.candidate_placement_history import CandidatePlacementHistory  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.client_job_access import ClientJobAccess  # noqa: F401
from app.models.client_recruiter_assignment import ClientRecruiterAssignment  # noqa: F401
from app.models.interview import (  # noqa: F401
    Interview,
    InterviewFeedback,
    InterviewNote,
    InterviewParticipant,
    InterviewerProfile,
    InterviewerSkill,
    InterviewerAvailability,
)
from app.models.interview_copilot import (  # noqa: F401
    InterviewCopilotSession,
    InterviewTranscriptSegment,
    InterviewAISuggestion,
)
from app.models.interview_reminder import InterviewReminder  # noqa: F401
from app.models.invite import Invite  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.job_match_cache import JobMatchCache  # noqa: F401
from app.models.job_skill import JobSkill  # noqa: F401
from app.models.job_status_history import JobStatusHistory  # noqa: F401
from app.models.job_submission import JobSubmission  # noqa: F401
from app.models.job_vendor import JobVendor  # noqa: F401
from app.models.offer import PipelineOffer, PipelineOfferEvent  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.organization_role import OrganizationRole  # noqa: F401
from app.models.permission import Permission  # noqa: F401
from app.models.pipeline import Pipeline, PipelineStageHistory, PipelineStatusHistory  # noqa: F401
from app.models.profile import Profile  # noqa: F401
from app.models.role_permission import RolePermission  # noqa: F401
from app.models.sourcing_session import SourcingSession, SourcingResult  # noqa: F401

# candidate_management/ has its own isolated DeclarativeBase (see module
# docstring) — its tables are not on Base.metadata and are intentionally
# NOT included in target_metadata below; autogenerate for this Base only
# ever compares the app.models.* tables.
import app.candidate_management.models as _candidate_management_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
logger = logging.getLogger(__name__)

# Use DATABASE_URL from .env instead of hardcoded alembic.ini URL.
# ConfigParser treats '%' as interpolation; escape for URL-encoded passwords.
if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
config.set_main_option("sqlalchemy.hide_parameters", "true")
logger.debug("Alembic configured for DB URL: %s", redact_database_url(settings.database_url))

# IMPORTANT:
# Use declarative metadata (model code) for stable, deterministic autogenerate.
# Do not use runtime reflection metadata here, which can cause noisy/false diffs.
target_metadata = Base.metadata


def _process_revision_directives(_context, _revision, directives) -> None:
    """
    Safety guard: when `alembic revision --autogenerate` detects no schema changes,
    skip creating an empty migration file.
    """
    cmd_opts = getattr(config, "cmd_opts", None)
    if not cmd_opts or not getattr(cmd_opts, "autogenerate", False):
        return
    if not directives:
        return
    script = directives[0]
    if script.upgrade_ops.is_empty():
        directives[:] = []
        logger.info("No schema changes detected; migration file not generated.")


_COMPARE_SERVER_DEFAULT = os.getenv("ALEMBIC_COMPARE_SERVER_DEFAULT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=_COMPARE_SERVER_DEFAULT,
        # Schema-per-service (see 0001_initial.py): tables span 10+ Postgres
        # schemas, each declared per-model via __table_args__. Autogenerate
        # must consider all schemas, not just a single configured db_schema.
        include_schemas=True,
        # alembic_version stays wherever it was originally stamped
        # (settings.db_schema, historically unset -> default/public) so we
        # don't orphan the already-applied 0001_initial revision tracking.
        version_table_schema=settings.db_schema,
        process_revision_directives=_process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        hide_parameters=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=_COMPARE_SERVER_DEFAULT,
            include_schemas=bool(settings.db_schema),
            version_table_schema=settings.db_schema,
            process_revision_directives=_process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

