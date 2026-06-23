"""breakthrough canvas stages

Revision ID: 202606170001
Revises: 202606160002
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606170001"
down_revision: str | None = "202606160002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _uuid_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _json_default(value: str) -> sa.TextClause:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text(f"'{value}'::jsonb")
    return sa.text(f"'{value}'")


def _uuid_default() -> sa.TextClause | None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("gen_random_uuid()")
    return None


def upgrade() -> None:
    uuid_type = _uuid_type()
    json_type = _json_type()

    op.add_column("writing_sessions", sa.Column("structured_payload", json_type, nullable=False, server_default=_json_default("{}")))
    op.add_column("writing_sessions", sa.Column("pipeline_version", sa.Text(), nullable=True))
    op.add_column(
        "writing_sessions",
        sa.Column("decision_stage_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "writing_session_stages",
        sa.Column("id", uuid_type, primary_key=True, server_default=_uuid_default()),
        sa.Column("writing_session_id", uuid_type, sa.ForeignKey("writing_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("module_type", card_module_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("prompt_label", sa.Text(), nullable=True),
        sa.Column("ghost_starter", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="completed"),
        sa.Column("idle_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("interruption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nudges_shown", json_type, nullable=False, server_default=_json_default("[]")),
        sa.Column("metadata_json", json_type, nullable=False, server_default=_json_default("{}")),
        sa.Column("created_card_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_writing_session_stages_session_id", "writing_session_stages", ["writing_session_id"])
    op.create_index("idx_writing_session_stages_stage_id", "writing_session_stages", ["stage_id"])

    op.add_column("cognitive_cards", sa.Column("source_session_id", uuid_type, sa.ForeignKey("writing_sessions.id"), nullable=True))
    op.add_column("cognitive_cards", sa.Column("source_stage_id", uuid_type, sa.ForeignKey("writing_session_stages.id"), nullable=True))
    op.create_index("idx_cards_source_session_id", "cognitive_cards", ["source_session_id"])
    op.create_index("idx_cards_source_stage_id", "cognitive_cards", ["source_stage_id"])

    op.add_column("time_capsules", sa.Column("source_session_id", uuid_type, sa.ForeignKey("writing_sessions.id"), nullable=True))
    op.add_column("time_capsules", sa.Column("source_stage_id", uuid_type, sa.ForeignKey("writing_session_stages.id"), nullable=True))
    op.create_index("idx_time_capsules_source_session_id", "time_capsules", ["source_session_id"])
    op.create_index("idx_time_capsules_source_stage_id", "time_capsules", ["source_stage_id"])


def downgrade() -> None:
    op.drop_index("idx_time_capsules_source_stage_id", table_name="time_capsules")
    op.drop_index("idx_time_capsules_source_session_id", table_name="time_capsules")
    op.drop_column("time_capsules", "source_stage_id")
    op.drop_column("time_capsules", "source_session_id")

    op.drop_index("idx_cards_source_stage_id", table_name="cognitive_cards")
    op.drop_index("idx_cards_source_session_id", table_name="cognitive_cards")
    op.drop_column("cognitive_cards", "source_stage_id")
    op.drop_column("cognitive_cards", "source_session_id")

    op.drop_index("idx_writing_session_stages_stage_id", table_name="writing_session_stages")
    op.drop_index("idx_writing_session_stages_session_id", table_name="writing_session_stages")
    op.drop_table("writing_session_stages")

    op.drop_column("writing_sessions", "decision_stage_enabled")
    op.drop_column("writing_sessions", "pipeline_version")
    op.drop_column("writing_sessions", "structured_payload")
