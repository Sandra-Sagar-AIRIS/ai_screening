"""PIPE-008: Offer Management — create pipeline_offers and pipeline_offer_events tables.

pipeline_offers     — one row per offer; tracks salary, dates, response lifecycle.
pipeline_offer_events — immutable audit log; one row per offer lifecycle event.

Revision ID: 20260519_0006
Revises: 20260519_0005
Create Date: 2026-05-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "20260519_0006"
down_revision: str = "20260519_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pipeline_offers ───────────────────────────────────────────────────────
    op.create_table(
        "pipeline_offers",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "pipeline_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("job_id", PGUUID(as_uuid=True), nullable=False),
        # Offer details (AC: offered_salary, offer_date, expiry_date, currency)
        sa.Column("offered_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("offer_date", sa.Date, nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=False),
        # Candidate response: pending | accepted | declined | negotiating
        sa.Column("offer_response", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decline_reason", sa.Text, nullable=True),
        # Stage before offer — stored to support optional revert on decline.
        sa.Column("previous_stage", sa.String(80), nullable=True),
        # Expiry alert tracking.
        sa.Column("expiry_alert_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", PGUUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes for common query patterns.
    op.create_index("ix_pipeline_offers_organization_id", "pipeline_offers", ["organization_id"])
    op.create_index("ix_pipeline_offers_pipeline_id", "pipeline_offers", ["pipeline_id"])
    op.create_index("ix_pipeline_offers_candidate_id", "pipeline_offers", ["candidate_id"])
    op.create_index("ix_pipeline_offers_job_id", "pipeline_offers", ["job_id"])
    # Index to speed up expiry alert scan.
    op.create_index(
        "ix_pipeline_offers_expiry_alert_pending",
        "pipeline_offers",
        ["expiry_date", "expiry_alert_sent", "offer_response"],
    )

    # ── pipeline_offer_events ─────────────────────────────────────────────────
    op.create_table(
        "pipeline_offer_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "pipeline_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "offer_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pipeline_offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("previous_response", sa.String(20), nullable=True),
        sa.Column("new_response", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_pipeline_offer_events_organization_id", "pipeline_offer_events", ["organization_id"])
    op.create_index("ix_pipeline_offer_events_pipeline_id", "pipeline_offer_events", ["pipeline_id"])
    op.create_index("ix_pipeline_offer_events_offer_id", "pipeline_offer_events", ["offer_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_offer_events_offer_id", table_name="pipeline_offer_events")
    op.drop_index("ix_pipeline_offer_events_pipeline_id", table_name="pipeline_offer_events")
    op.drop_index("ix_pipeline_offer_events_organization_id", table_name="pipeline_offer_events")
    op.drop_table("pipeline_offer_events")

    op.drop_index("ix_pipeline_offers_expiry_alert_pending", table_name="pipeline_offers")
    op.drop_index("ix_pipeline_offers_job_id", table_name="pipeline_offers")
    op.drop_index("ix_pipeline_offers_candidate_id", table_name="pipeline_offers")
    op.drop_index("ix_pipeline_offers_pipeline_id", table_name="pipeline_offers")
    op.drop_index("ix_pipeline_offers_organization_id", table_name="pipeline_offers")
    op.drop_table("pipeline_offers")
