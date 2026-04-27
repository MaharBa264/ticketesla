"""add structured ticket data

Revision ID: 20260427_0002
Revises: 20260424_0001
Create Date: 2026-04-27 11:40:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260427_0002"
down_revision = "20260424_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("structured_data", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("tickets", "structured_data")
