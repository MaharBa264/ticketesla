"""Allow admin-created users without Gmail.

Revision ID: 20260427_0004
Revises: 20260427_0003
Create Date: 2026-04-27 09:05:00
"""
from alembic import op
import sqlalchemy as sa


revision = "20260427_0004"
down_revision = "20260427_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users",
        "gmail",
        existing_type=sa.String(length=160),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "users",
        "gmail",
        existing_type=sa.String(length=160),
        nullable=False,
    )
