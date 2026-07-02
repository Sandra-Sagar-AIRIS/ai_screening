"""ORM model for identity.auth_security_logs (login/MFA/session security events)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


auth_security_event_type_enum = sa.Enum(
    "invalid_signature",
    "expired",
    "version_mismatch",
    "revoked_session",
    "rate_limit",
    "invalid_invite",
    "expired_invite",
    "reused_invite",
    "unknown",
    name="auth_security_event_type",
    schema="identity",
    create_type=False,
)


class AuthSecurityLog(Base):
    __tablename__ = "auth_security_logs"
    __table_args__ = {"schema": "identity"}

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(auth_security_event_type_enum, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
