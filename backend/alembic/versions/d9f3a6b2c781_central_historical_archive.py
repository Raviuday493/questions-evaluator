"""central historical question and solution archive

Revision ID: d9f3a6b2c781
Revises: c4e8a1f2b9d0
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9f3a6b2c781"
down_revision: Union[str, Sequence[str], None] = "c4e8a1f2b9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "archive_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("source_reference", sa.String(512), nullable=True),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("ingested_by_id", sa.Uuid(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["ingested_by_id"], ["admin_users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_hash", "source_key", name="uq_archive_question_source_hash"
        ),
    )
    op.create_index(
        "ix_archive_questions_content_hash", "archive_questions", ["content_hash"]
    )
    op.create_index(
        "ix_archive_questions_topic_created",
        "archive_questions",
        ["topic", "ingested_at"],
    )
    op.create_index(
        "ix_archive_questions_subject_created",
        "archive_questions",
        ["subject", "ingested_at"],
    )
    op.create_table(
        "archive_solutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("solution_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"], ["archive_questions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_id", "content_hash", name="uq_archive_solution_question_hash"
        ),
    )
    op.create_index(
        "ix_archive_solutions_question", "archive_solutions", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_archive_solutions_question", table_name="archive_solutions")
    op.drop_table("archive_solutions")
    op.drop_index(
        "ix_archive_questions_subject_created", table_name="archive_questions"
    )
    op.drop_index("ix_archive_questions_topic_created", table_name="archive_questions")
    op.drop_index("ix_archive_questions_content_hash", table_name="archive_questions")
    op.drop_table("archive_questions")
