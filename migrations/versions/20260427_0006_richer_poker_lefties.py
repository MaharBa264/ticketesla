"""richer poker lefties mechanics

Revision ID: 20260427_0006
Revises: 20260427_0005
Create Date: 2026-04-27 12:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260427_0006"
down_revision = "20260427_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_user_settings", sa.Column("ranking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("game_user_states", sa.Column("streak_current", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_user_states", sa.Column("streak_best", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_user_states", sa.Column("best_hand_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_user_states", sa.Column("last_streak_date", sa.Date(), nullable=True))
    op.add_column("game_hands", sa.Column("base_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_hands", sa.Column("bonuses_json", sa.JSON(), nullable=True))
    op.add_column("game_hands", sa.Column("multiplier", sa.Float(), nullable=False, server_default="1.0"))

    op.create_table(
        "game_jokers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("unlock_rule", sa.String(length=160), nullable=False),
        sa.Column("effect_json", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_game_jokers_code", "game_jokers", ["code"])

    op.create_table(
        "game_user_jokers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("joker_id", sa.Integer(), sa.ForeignKey("game_jokers.id"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equipped_slot", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "joker_id", name="uq_game_user_joker"),
    )
    op.create_index("ix_game_user_jokers_user_id", "game_user_jokers", ["user_id"])

    op.create_table(
        "game_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("condition_key", sa.String(length=80), nullable=False),
        sa.Column("points_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_game_achievements_code", "game_achievements", ["code"])

    op.create_table(
        "game_user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("game_achievements.id"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_game_user_achievement"),
    )
    op.create_index("ix_game_user_achievements_user_id", "game_user_achievements", ["user_id"])


def downgrade():
    op.drop_index("ix_game_user_achievements_user_id", table_name="game_user_achievements")
    op.drop_table("game_user_achievements")
    op.drop_index("ix_game_achievements_code", table_name="game_achievements")
    op.drop_table("game_achievements")
    op.drop_index("ix_game_user_jokers_user_id", table_name="game_user_jokers")
    op.drop_table("game_user_jokers")
    op.drop_index("ix_game_jokers_code", table_name="game_jokers")
    op.drop_table("game_jokers")
    op.drop_column("game_hands", "multiplier")
    op.drop_column("game_hands", "bonuses_json")
    op.drop_column("game_hands", "base_score")
    op.drop_column("game_user_states", "last_streak_date")
    op.drop_column("game_user_states", "best_hand_score")
    op.drop_column("game_user_states", "streak_best")
    op.drop_column("game_user_states", "streak_current")
    op.drop_column("game_user_settings", "ranking_enabled")
