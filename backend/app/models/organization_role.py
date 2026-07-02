from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationRole(Base):
    """
    Tenant-defined role (system defaults + custom).
    `key` is a stable slug used in APIs and JWT (`profile.role` mirrors this).
    """

    __tablename__ = "organization_roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_organization_roles_org_key"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
