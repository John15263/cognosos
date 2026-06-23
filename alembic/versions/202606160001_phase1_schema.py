"""phase 1 schema

Revision ID: 202606160001
Revises:
Create Date: 2026-06-16
"""

from collections.abc import Sequence
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

revision: str = "202606160001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"


raw_entry_source = sa.Enum(
    "text",
    "voice",
    "import",
    name="raw_entry_source",
    native_enum=False,
    create_constraint=True,
)
processing_status = sa.Enum(
    "received",
    "processed",
    "failed",
    name="processing_status",
    native_enum=False,
    create_constraint=True,
)
card_module_type = sa.Enum(
    "free_write",
    "decision",
    "gratitude",
    "reciprocity",
    "scaffolding",
    "avsi",
    "future_self",
    "check_review",
    "task",
    "insight",
    "general",
    name="card_module_type",
    native_enum=False,
    create_constraint=True,
)
card_status = sa.Enum(
    "open",
    "closed",
    "archived",
    "stalled",
    "waiting",
    "dismissed",
    name="card_status",
    native_enum=False,
    create_constraint=True,
)
privacy_level = sa.Enum(
    "private",
    "sensitive",
    "normal",
    "public",
    name="privacy_level",
    native_enum=False,
    create_constraint=True,
)
time_capsule_action_type = sa.Enum(
    "check_decision",
    "return_kindness",
    "review_scaffold",
    "review_future_self",
    "review_avsi_followup",
    "general_reminder",
    name="time_capsule_action_type",
    native_enum=False,
    create_constraint=True,
)
time_capsule_status = sa.Enum(
    "pending",
    "triggered",
    "resolved",
    "dismissed",
    name="time_capsule_status",
    native_enum=False,
    create_constraint=True,
)
trigger_module_type = sa.Enum(
    "decision",
    "scaffolding",
    "avsi",
    "future_self",
    "reciprocity",
    "check_review",
    name="trigger_module_type",
    native_enum=False,
    create_constraint=True,
)
trigger_event_status = sa.Enum(
    "suggested",
    "accepted",
    "dismissed",
    "completed",
    name="trigger_event_status",
    native_enum=False,
    create_constraint=True,
)
module_run_status = sa.Enum(
    "started",
    "completed",
    "cancelled",
    "failed",
    name="module_run_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "raw_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", raw_entry_source, nullable=False, server_default="text"),
        sa.Column("processing_status", processing_status, nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "cognitive_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_entries.id"), nullable=True),
        sa.Column("module_type", card_module_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_for_embedding", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("emotion_score", sa.Integer(), nullable=True),
        sa.Column("importance_score", sa.Integer(), nullable=True),
        sa.Column("urgency_score", sa.Integer(), nullable=True),
        sa.Column("status", card_status, nullable=False, server_default="open"),
        sa.Column("privacy_level", privacy_level, nullable=False, server_default="private"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("emotion_score IS NULL OR (emotion_score >= 0 AND emotion_score <= 10)", name="ck_cards_emotion_score"),
        sa.CheckConstraint("importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 10)", name="ck_cards_importance_score"),
        sa.CheckConstraint("urgency_score IS NULL OR (urgency_score >= 0 AND urgency_score <= 10)", name="ck_cards_urgency_score"),
    )
    op.create_index("idx_cards_created_at", "cognitive_cards", ["created_at"])
    op.create_index("idx_cards_status", "cognitive_cards", ["status"])
    op.create_index("idx_cards_module_type", "cognitive_cards", ["module_type"])
    op.create_index("idx_cards_metadata_json_gin", "cognitive_cards", ["metadata_json"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX idx_cards_embedding_hnsw "
        "ON cognitive_cards USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )

    op.create_table(
        "time_capsules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cognitive_cards.id"), nullable=True),
        sa.Column("action_type", time_capsule_action_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", time_capsule_status, nullable=False, server_default="pending"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_time_capsules_trigger_at", "time_capsules", ["trigger_at"])
    op.create_index("idx_time_capsules_status", "time_capsules", ["status"])

    op.create_table(
        "trigger_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("triggered_module", trigger_module_type, nullable=False),
        sa.Column("current_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cognitive_cards.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_card_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("intervention_level", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("status", trigger_event_status, nullable=False, server_default="suggested"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("intervention_level >= 0 AND intervention_level <= 3", name="ck_trigger_events_intervention_level"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_trigger_events_confidence"),
    )

    op.create_table(
        "module_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("module_type", trigger_module_type, nullable=False),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trigger_events.id"), nullable=True),
        sa.Column("input_card_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_card_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_time_capsule_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", module_run_status, nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("module_runs")
    op.drop_table("trigger_events")
    op.drop_index("idx_time_capsules_status", table_name="time_capsules")
    op.drop_index("idx_time_capsules_trigger_at", table_name="time_capsules")
    op.drop_table("time_capsules")
    op.execute("DROP INDEX IF EXISTS idx_cards_embedding_hnsw")
    op.drop_index("idx_cards_metadata_json_gin", table_name="cognitive_cards")
    op.drop_index("idx_cards_module_type", table_name="cognitive_cards")
    op.drop_index("idx_cards_status", table_name="cognitive_cards")
    op.drop_index("idx_cards_created_at", table_name="cognitive_cards")
    op.drop_table("cognitive_cards")
    op.drop_table("raw_entries")

