"""admin panel: admin accounts, roles, sessions, runtime settings; audit/user columns

Revision ID: c4e8a1f2b9d0
Revises: b7c1d2e3f4a5
Create Date: 2026-09-30 20:00:00

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.admin_permissions import SYSTEM_ROLES

revision: str = "c4e8a1f2b9d0"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    admin_roles = op.create_table(
        "admin_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("permissions", JSON, nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["admin_roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_admin_sessions_admin_created", "admin_sessions", ["admin_id", "created_at"], unique=False)
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )

    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("admin_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("entity_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("user_agent", sa.String(length=255), nullable=True))
        batch.create_foreign_key("fk_audit_logs_admin_id", "admin_users", ["admin_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_audit_logs_admin_created", "audit_logs", ["admin_id", "created_at"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False)

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("sessions_invalidated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    op.create_index("ix_papers_status_created", "question_paper_drafts", ["status", "created_at"], unique=False)
    op.create_index("ix_papers_created_at", "question_paper_drafts", ["created_at"], unique=False)

    now = datetime.now(timezone.utc)
    op.bulk_insert(admin_roles, [
        {"id": uuid.uuid4(), "key": key, "name": name, "description": description, "permissions": list(perms),
         "is_system": True, "created_at": now, "updated_at": now}
        for key, (name, description, perms) in SYSTEM_ROLES.items()
    ])


def downgrade() -> None:
    op.drop_index("ix_papers_created_at", table_name="question_paper_drafts")
    op.drop_index("ix_papers_status_created", table_name="question_paper_drafts")
    op.drop_index("ix_users_created_at", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("sessions_invalidated_at")
        batch.drop_column("last_login_at")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_admin_created", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("fk_audit_logs_admin_id", type_="foreignkey")
        batch.drop_column("user_agent")
        batch.drop_column("entity_type")
        batch.drop_column("admin_id")
    op.drop_table("app_settings")
    op.drop_index("ix_admin_sessions_admin_created", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admin_users")
    op.drop_table("admin_roles")
