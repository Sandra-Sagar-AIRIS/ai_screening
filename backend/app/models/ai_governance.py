"""SQLAlchemy ORM models for the AI Governance / cost-metering layer.

Six tables (schema `ai`), all metering/governance concerns for AI usage:
  ai_request_log            — per-call cost/usage ledger
  ai_rate_limit_log          — rate-limit block events
  ai_cost_alerts             — per-org monthly threshold alerts
  ai_model_pricing_master    — provider/model pricing catalog
  ai_log_retention_config    — per-org log retention policy
  ai_log_cleanup_audit       — retention sweep execution audit trail
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


ai_pricing_status_enum = sa.Enum(
    "configured",
    "unknown",
    "estimated",
    name="ai_pricing_status",
    schema="ai",
    create_type=False,
)

ai_request_status_enum = sa.Enum(
    "success",
    "failed",
    "timeout",
    "cancelled",
    "rate_limited",
    "partial",
    name="ai_request_status",
    schema="ai",
    create_type=False,
)


class AIRequestLog(Base):
    """Per-call AI usage/cost ledger, written by every AI-producing service."""

    __tablename__ = "ai_request_log"
    __table_args__ = {"schema": "ai"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # organization_id is a cross-schema reference (identity.organizations) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    function_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credits_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    input_cost_rate: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    output_cost_rate: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    pricing_unit: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("1000000"))
    pricing_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pricing_status: Mapped[str] = mapped_column(
        ai_pricing_status_enum, nullable=False, server_default=sa.text("'configured'")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=sa.text("'USD'"))
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    request_status: Mapped[str] = mapped_column(ai_request_status_enum, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIRateLimitLog(Base):
    """Rate-limit block events (id is BIGSERIAL, not UUID, in the DB)."""

    __tablename__ = "ai_rate_limit_log"
    __table_args__ = {"schema": "ai"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    organization_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    blocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class AICostAlert(Base):
    """Per-organization monthly AI-cost threshold alert."""

    __tablename__ = "ai_cost_alerts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "billing_month", "alert_type", name="uq_ai_cost_alert_org_month_type"
        ),
        {"schema": "ai"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # organization_id is a cross-schema reference (identity.organizations) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sa.text("'pending'")
    )
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AIModelPricingMaster(Base):
    """Provider/model pricing catalog."""

    __tablename__ = "ai_model_pricing_master"
    __table_args__ = {"schema": "ai"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_rate_per_million_tokens: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    output_rate_per_million_tokens: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AILogRetentionConfig(Base):
    """Per-organization AI log retention policy (null org_id = global default)."""

    __tablename__ = "ai_log_retention_config"
    __table_args__ = {"schema": "ai"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    # organization_id is a cross-schema reference (identity.organizations) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    organization_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, unique=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("730"))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AILogCleanupAudit(Base):
    """Execution audit trail for the AI log retention/cleanup sweep."""

    __tablename__ = "ai_log_cleanup_audit"
    __table_args__ = {"schema": "ai"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    retention_days_used: Mapped[int] = mapped_column(Integer, nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False)
    records_soft_deleted: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    execution_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
