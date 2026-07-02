from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "identity"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(64), nullable=False, server_default=sa.text("'trial'"))
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("3"))
    max_concurrent_sessions: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    screening_reminders_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    ai_monthly_cost_threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    ai_threshold_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    ai_alert_recipient_emails: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    ai_threshold_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_threshold_updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    billing_timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=sa.text("'UTC'"))
    dpdpa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    dpdpa_grievance_officer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dpdpa_grievance_officer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_localization_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
