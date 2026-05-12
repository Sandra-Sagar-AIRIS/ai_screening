from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    DDL,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import get_settings


def _module_metadata() -> sa.MetaData:
    schema = get_settings().db_schema
    return sa.MetaData(schema=schema) if schema else sa.MetaData()


class Base(DeclarativeBase):
    """Isolated declarative base to avoid metadata collisions."""

    metadata = _module_metadata()


class CandidateSource(str, enum.Enum):
    MANUAL = "manual"
    RESUME_UPLOAD = "resume_upload"
    BULK_UPLOAD = "bulk_upload"
    REFERRAL = "referral"
    AGENCY = "agency"
    IMPORT = "import"
    MERGE = "merge"


class CandidateStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class InteractionType(str, enum.Enum):
    NOTE = "note"
    EMAIL = "email"
    STAGE_CHANGE = "stage_change"
    INTERVIEW = "interview"
    SYSTEM = "system"


class CommunicationProvider(str, enum.Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    WHATSAPP = "whatsapp"


class CommunicationChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class CommunicationMessageDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class CommunicationMessageStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    REPLIED = "replied"
    FAILED = "failed"


class BulkUploadStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BulkUploadItemStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"


class CandidateParseStatus(str, enum.Enum):
    """Lifecycle of resume parsing for a candidate.

    `pending`     - row exists, parser hasn't run yet.
    `processing`  - parser running (set immediately before invocation).
    `completed`   - parser succeeded; structured fields populated.
    `failed`      - parser raised; `parse_error` holds the message.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidates_org_email_active", "org_id", "email", postgresql_where=sa.text("deleted_at IS NULL")),
        Index("ix_candidates_org_phone_active", "org_id", "phone", postgresql_where=sa.text("deleted_at IS NULL")),
        Index("ix_candidates_org_workspace_created_at", "org_id", "workspace_id", "created_at"),
        UniqueConstraint("id", "org_id", "workspace_id", name="uq_candidates_id_org_workspace"),
        CheckConstraint("years_experience >= 0", name="ck_candidates_years_experience_non_negative"),
        CheckConstraint(
            "(parse_confidence IS NULL) OR (parse_confidence >= 0 AND parse_confidence <= 1)",
            name="ck_candidates_parse_confidence_between_0_1",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    full_name: Mapped[str] = mapped_column(String(260), nullable=False)

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="applied", server_default="applied")
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)

    source: Mapped[CandidateSource] = mapped_column(
        sa.String(40),
        nullable=False,
        default=CandidateSource.MANUAL,
        server_default=CandidateSource.MANUAL.value,
    )
    status: Mapped[CandidateStatus] = mapped_column(
        sa.String(40),
        nullable=False,
        default=CandidateStatus.ACTIVE,
        server_default=CandidateStatus.ACTIVE.value,
    )

    resume_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resume_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_parse_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    parsed_resume_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # ATS resume-parsing lifecycle (separate from AI confidence).
    parse_status: Mapped[CandidateParseStatus] = mapped_column(
        sa.String(20),
        nullable=False,
        default=CandidateParseStatus.PENDING,
        server_default=CandidateParseStatus.PENDING.value,
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    merged_into_candidate_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    recruiter_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    deleted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    skills: Mapped[list["CandidateSkill"]] = relationship(
        "CandidateSkill",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    interactions: Mapped[list["CandidateInteraction"]] = relationship(
        "CandidateInteraction",
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateInteraction.created_at",
    )
    audit_logs: Mapped[list["CandidateAuditLog"]] = relationship(
        "CandidateAuditLog",
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateAuditLog.created_at",
    )


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (
        UniqueConstraint("candidate_id", "normalized_name", name="uq_candidate_skills_candidate_normalized_name"),
        Index("ix_candidate_skills_org_workspace_name", "org_id", "workspace_id", "normalized_name"),
        CheckConstraint("(confidence IS NULL) OR (confidence >= 0 AND confidence <= 1)", name="ck_candidate_skills_confidence"),
        ForeignKeyConstraint(
            ["candidate_id", "org_id", "workspace_id"],
            ["candidates.id", "candidates.org_id", "candidates.workspace_id"],
            ondelete="CASCADE",
            name="fk_candidate_skills_candidate_tenant",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(30), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="manual")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="skills")


class CandidateInteraction(Base):
    __tablename__ = "candidate_interactions"
    __table_args__ = (
        Index("ix_candidate_interactions_org_workspace_created_at", "org_id", "workspace_id", "created_at"),
        Index("ix_candidate_interactions_candidate_created_at", "candidate_id", "created_at"),
        ForeignKeyConstraint(
            ["candidate_id", "org_id", "workspace_id"],
            ["candidates.id", "candidates.org_id", "candidates.workspace_id"],
            ondelete="CASCADE",
            name="fk_candidate_interactions_candidate_tenant",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    interaction_type: Mapped[InteractionType] = mapped_column(
        "type",
        Enum(InteractionType, name="candidate_interaction_type", native_enum=False),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="interactions")


class CandidateAuditLog(Base):
    __tablename__ = "candidate_audit_logs"
    __table_args__ = (
        Index("ix_candidate_audit_log_org_workspace_created_at", "org_id", "workspace_id", "created_at"),
        Index("ix_candidate_audit_log_candidate_created_at", "candidate_id", "created_at"),
        ForeignKeyConstraint(
            ["candidate_id", "org_id", "workspace_id"],
            ["candidates.id", "candidates.org_id", "candidates.workspace_id"],
            ondelete="CASCADE",
            name="fk_candidate_audit_log_candidate_tenant",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="audit_logs")


class CommunicationConnection(Base):
    __tablename__ = "comm_connections"
    __table_args__ = (
        Index("ix_comm_connections_org_workspace_provider", "org_id", "workspace_id", "provider"),
        UniqueConstraint(
            "org_id",
            "workspace_id",
            "provider",
            "external_account_id",
            name="uq_comm_connections_account_provider",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    provider: Mapped[CommunicationProvider] = mapped_column(
        Enum(CommunicationProvider, name="communication_provider", native_enum=False),
        nullable=False,
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
        server_default=CommunicationChannel.EMAIL.value,
    )
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="connected")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CommunicationTemplate(Base):
    __tablename__ = "comm_templates"
    __table_args__ = (
        Index("ix_comm_templates_org_workspace_channel", "org_id", "workspace_id", "channel"),
        UniqueConstraint(
            "org_id",
            "workspace_id",
            "channel",
            "name",
            name="uq_comm_templates_name_per_channel",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
        server_default=CommunicationChannel.EMAIL.value,
    )
    provider: Mapped[CommunicationProvider | None] = mapped_column(
        Enum(CommunicationProvider, name="communication_provider", native_enum=False),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    placeholders: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CommunicationMessage(Base):
    __tablename__ = "comm_messages"
    __table_args__ = (
        Index("ix_comm_messages_org_workspace_candidate_created", "org_id", "workspace_id", "candidate_id", "created_at"),
        Index("ix_comm_messages_org_workspace_status", "org_id", "workspace_id", "status"),
        UniqueConstraint(
            "org_id",
            "workspace_id",
            "provider",
            "provider_message_id",
            name="uq_comm_messages_provider_message_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
        server_default=CommunicationChannel.EMAIL.value,
    )
    provider: Mapped[CommunicationProvider] = mapped_column(
        Enum(CommunicationProvider, name="communication_provider", native_enum=False),
        nullable=False,
    )
    direction: Mapped[CommunicationMessageDirection] = mapped_column(
        Enum(CommunicationMessageDirection, name="communication_message_direction", native_enum=False),
        nullable=False,
        server_default=CommunicationMessageDirection.OUTBOUND.value,
    )
    status: Mapped[CommunicationMessageStatus] = mapped_column(
        Enum(CommunicationMessageStatus, name="communication_message_status", native_enum=False),
        nullable=False,
        server_default=CommunicationMessageStatus.QUEUED.value,
    )
    to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("comm_templates.id"), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CommunicationMessageEvent(Base):
    __tablename__ = "comm_message_events"
    __table_args__ = (
        Index("ix_comm_message_events_message_created", "message_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comm_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CommunicationReminder(Base):
    __tablename__ = "comm_reminders"
    __table_args__ = (
        Index("ix_comm_reminders_org_workspace_due", "org_id", "workspace_id", "scheduled_for"),
        Index("ix_comm_reminders_status_scheduled", "status", "scheduled_for"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
        server_default=CommunicationChannel.EMAIL.value,
    )
    provider: Mapped[CommunicationProvider] = mapped_column(
        Enum(CommunicationProvider, name="communication_provider", native_enum=False),
        nullable=False,
    )
    template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("comm_templates.id"), nullable=True)
    to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BulkUploadJob(Base):
    __tablename__ = "bulk_upload_jobs"
    __table_args__ = (
        Index("ix_bulk_upload_jobs_org_workspace_created_at", "org_id", "workspace_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    status: Mapped[BulkUploadStatus] = mapped_column(
        Enum(BulkUploadStatus, name="bulk_upload_status", native_enum=False),
        nullable=False,
        default=BulkUploadStatus.PENDING,
        server_default=BulkUploadStatus.PENDING.value,
    )
    requested_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["BulkUploadItem"]] = relationship(
        "BulkUploadItem",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="BulkUploadItem.created_at",
    )


class BulkUploadItem(Base):
    __tablename__ = "bulk_upload_items"
    __table_args__ = (
        Index("ix_bulk_upload_items_job_status", "job_id", "status"),
        Index("ix_bulk_upload_items_org_workspace_created_at", "org_id", "workspace_id", "created_at"),
        ForeignKeyConstraint(
            ["job_id", "org_id", "workspace_id"],
            ["bulk_upload_jobs.id", "bulk_upload_jobs.org_id", "bulk_upload_jobs.workspace_id"],
            ondelete="CASCADE",
            name="fk_bulk_upload_items_job_tenant",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "org_id", "workspace_id"],
            ["candidates.id", "candidates.org_id", "candidates.workspace_id"],
            ondelete="NO ACTION",
            name="fk_bulk_upload_items_candidate_tenant",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[BulkUploadItemStatus] = mapped_column(
        Enum(BulkUploadItemStatus, name="bulk_upload_item_status", native_enum=False),
        nullable=False,
        default=BulkUploadItemStatus.PENDING,
        server_default=BulkUploadItemStatus.PENDING.value,
    )

    extracted_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    extracted_phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    parse_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["BulkUploadJob"] = relationship("BulkUploadJob", back_populates="items")


event.listen(
    CandidateInteraction.__table__,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION prevent_candidate_interactions_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'candidate_interactions is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    ),
)
event.listen(
    CandidateInteraction.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_candidate_interactions_no_update
        BEFORE UPDATE ON candidate_interactions
        FOR EACH ROW EXECUTE FUNCTION prevent_candidate_interactions_mutation();
        """
    ),
)
event.listen(
    CandidateInteraction.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_candidate_interactions_no_delete
        BEFORE DELETE ON candidate_interactions
        FOR EACH ROW EXECUTE FUNCTION prevent_candidate_interactions_mutation();
        """
    ),
)

event.listen(
    CandidateAuditLog.__table__,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION prevent_candidate_audit_log_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'candidate_audit_logs is immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    ),
)
event.listen(
    CandidateAuditLog.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_candidate_audit_log_no_update
        BEFORE UPDATE ON candidate_audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_candidate_audit_log_mutation();
        """
    ),
)
event.listen(
    CandidateAuditLog.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_candidate_audit_log_no_delete
        BEFORE DELETE ON candidate_audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_candidate_audit_log_mutation();
        """
    ),
)

