"""flow sessions and obsidian links

Revision ID: 202606160002
Revises: 202606160001
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606160002"
down_revision: str | None = "202606160001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


writing_session_mode = sa.Enum(
    "hard",
    "soft",
    "training",
    name="writing_session_mode",
    native_enum=False,
    create_constraint=True,
)
writing_session_status = sa.Enum(
    "started",
    "completed",
    "failed",
    "aborted",
    name="writing_session_status",
    native_enum=False,
    create_constraint=True,
)
obsidian_object_type = sa.Enum(
    "raw_entry",
    "cognitive_card",
    "trigger_event",
    "time_capsule",
    "module_run",
    "writing_session",
    name="obsidian_object_type",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "writing_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("prompt_id", sa.String(length=80), nullable=False),
        sa.Column("prompt_title", sa.Text(), nullable=False),
        sa.Column("prompt_cues", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mode", writing_session_mode, nullable=False, server_default="hard"),
        sa.Column("status", writing_session_status, nullable=False, server_default="started"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("idle_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("final_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interruption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("note_path", sa.Text(), nullable=True),
        sa.Column("raw_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_entries.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_writing_sessions_status", "writing_sessions", ["status"])
    op.create_index("idx_writing_sessions_started_at", "writing_sessions", ["started_at"])

    op.create_table(
        "obsidian_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("object_type", obsidian_object_type, nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_path", sa.Text(), nullable=False),
        sa.Column("block_id", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_obsidian_links_object", "obsidian_links", ["object_type", "object_id"])
    op.create_index("idx_obsidian_links_note_path", "obsidian_links", ["note_path"])


def downgrade() -> None:
    op.drop_index("idx_obsidian_links_note_path", table_name="obsidian_links")
    op.drop_index("idx_obsidian_links_object", table_name="obsidian_links")
    op.drop_table("obsidian_links")
    op.drop_index("idx_writing_sessions_started_at", table_name="writing_sessions")
    op.drop_index("idx_writing_sessions_status", table_name="writing_sessions")
    op.drop_table("writing_sessions")

