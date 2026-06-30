"""inbox_events (idempotent Pub/Sub event ledger)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbox_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=200), nullable=False, unique=True),
        sa.Column("payload", sa.String(length=8000), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("inbox_events")
