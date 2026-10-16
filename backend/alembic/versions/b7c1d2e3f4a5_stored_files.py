"""stored files table for database-backed storage

Revision ID: b7c1d2e3f4a5
Revises: 8dd89b033550
Create Date: 2026-09-29 03:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "8dd89b033550"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("path"),
    )


def downgrade() -> None:
    op.drop_table("stored_files")
