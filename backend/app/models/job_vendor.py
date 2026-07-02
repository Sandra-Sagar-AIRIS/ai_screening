from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobVendor(Base):
    __tablename__ = "job_vendors"
    __table_args__ = {"schema": "jobs"}

    # Composite PK: (job_id, vendor_id)
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("jobs.jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # vendor_id is a cross-schema reference (identity.profiles) —
    # 0001_initial.py defines no FK for it; integrity is enforced at the
    # service layer.
    vendor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

