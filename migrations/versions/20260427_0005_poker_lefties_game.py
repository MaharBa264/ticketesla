"""add poker lefties game tables

Revision ID: 20260427_0005
Revises: 20260427_0004
Create Date: 2026-04-27 10:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260427_0005"
down_revision = "20260427_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "game_user_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("hands_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("window_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "game_user_states",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("points_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hands_played_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_window_start", sa.DateTime(timezone=True)),
        sa.Column("hands_used_in_window", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_played_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "game_hands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dealt_cards_json", sa.JSON(), nullable=False),
        sa.Column("discarded_cards_json", sa.JSON(), nullable=False),
        sa.Column("final_cards_json", sa.JSON(), nullable=False),
        sa.Column("result_name", sa.String(length=80), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_game_hands_user_id", "game_hands", ["user_id"])
    op.create_index("ix_game_hands_played_at", "game_hands", ["played_at"])


def downgrade():
    op.drop_index("ix_game_hands_played_at", table_name="game_hands")
    op.drop_index("ix_game_hands_user_id", table_name="game_hands")
    op.drop_table("game_hands")
    op.drop_table("game_user_states")
    op.drop_table("game_user_settings")
