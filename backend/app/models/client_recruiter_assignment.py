from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClientRecruiterAssignment(Base):
    __tablename__ = "client_recruiter_assignments"
    __table_args__ = (
        UniqueConstraint("client_id", "recruiter_id", name="uq_client_recruiter"),
        {"schema": "jobs"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    client_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # recruiter_id is a cross-schema reference (identity.profiles) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    recruiter_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    assigned_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
