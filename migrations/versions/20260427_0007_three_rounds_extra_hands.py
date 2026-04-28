"""three discard rounds and extra hand grants

Revision ID: 20260427_0007
Revises: 20260427_0006
Create Date: 2026-04-27 14:10:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260427_0007"
down_revision = "20260427_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_user_states", sa.Column("best_result_name", sa.String(length=80), nullable=True))
    op.add_column("game_hands", sa.Column("discard_rounds_json", sa.JSON(), nullable=True))
    op.add_column("game_hands", sa.Column("bonuses_applied_json", sa.JSON(), nullable=True))
    op.add_column("game_hands", sa.Column("jokers_used_json", sa.JSON(), nullable=True))
    op.add_column("game_hands", sa.Column("score_breakdown_json", sa.JSON(), nullable=True))
    op.add_column("game_hands", sa.Column("bonus_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_hands", sa.Column("streak_bonus", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_hands", sa.Column("final_score", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE game_hands SET final_score = score WHERE final_score = 0")

    op.create_table(
        "game_hand_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("hands_granted", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hands_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "ticket_id", "action", name="uq_game_hand_grant_action"),
    )
    op.create_index("ix_game_hand_grants_user_id", "game_hand_grants", ["user_id"])
    op.create_index("ix_game_hand_grants_ticket_id", "game_hand_grants", ["ticket_id"])
    op.create_index("ix_game_hand_grants_expires_at", "game_hand_grants", ["expires_at"])


def downgrade():
    op.drop_index("ix_game_hand_grants_expires_at", table_name="game_hand_grants")
    op.drop_index("ix_game_hand_grants_ticket_id", table_name="game_hand_grants")
    op.drop_index("ix_game_hand_grants_user_id", table_name="game_hand_grants")
    op.drop_table("game_hand_grants")
    op.drop_column("game_hands", "final_score")
    op.drop_column("game_hands", "streak_bonus")
    op.drop_column("game_hands", "bonus_score")
    op.drop_column("game_hands", "score_breakdown_json")
    op.drop_column("game_hands", "jokers_used_json")
    op.drop_column("game_hands", "bonuses_applied_json")
    op.drop_column("game_hands", "discard_rounds_json")
    op.drop_column("game_user_states", "best_result_name")
