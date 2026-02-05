"""Add worklog settlement models

Revision ID: 2b4f8a9c1d5e
Revises: 1a31ce608336
Create Date: 2025-02-05

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2b4f8a9c1d5e"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade():
    # Create enums with raw SQL to avoid duplicate creation on retry
    op.execute(
        "DO $$ BEGIN CREATE TYPE timesegmentstatus AS ENUM ('ACTIVE', 'REMOVED'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE remittancestatus AS ENUM "
        "('PENDING', 'SUCCEEDED', 'FAILED', 'CANCELLED'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )

    timesegmentstatus = postgresql.ENUM(
        "ACTIVE", "REMOVED", name="timesegmentstatus", create_type=False
    )
    remittancestatus = postgresql.ENUM(
        "PENDING", "SUCCEEDED", "FAILED", "CANCELLED",
        name="remittancestatus", create_type=False
    )

    op.create_table(
        "task",
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "worklog",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "timesegment",
        sa.Column("worklog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("status", timesegmentstatus, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "adjustment",
        sa.Column("worklog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "remittance",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", remittancestatus, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "remittanceworklog",
        sa.Column("remittance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worklog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["remittance_id"], ["remittance.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worklog_id"], ["worklog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("remittanceworklog")
    op.drop_table("remittance")
    op.drop_table("adjustment")
    op.drop_table("timesegment")
    op.drop_table("worklog")
    op.drop_table("task")
    op.execute("DROP TYPE IF EXISTS remittancestatus CASCADE")
    op.execute("DROP TYPE IF EXISTS timesegmentstatus CASCADE")
