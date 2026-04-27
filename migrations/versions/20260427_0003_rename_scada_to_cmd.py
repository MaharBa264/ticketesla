"""rename SCADA area to CMD

Revision ID: 20260427_0003
Revises: 20260427_0002
Create Date: 2026-04-27
"""
from alembic import op

revision = "20260427_0003"
down_revision = "20260427_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE areas SET name = 'CMD' WHERE name = 'SCADA'")


def downgrade():
    op.execute("UPDATE areas SET name = 'SCADA' WHERE name = 'CMD'")
