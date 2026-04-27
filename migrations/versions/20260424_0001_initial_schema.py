"""initial schema

Revision ID: 20260424_0001
Revises:
Create Date: 2026-04-24 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260424_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("areas", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.create_table("permissions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.String(160)))
    op.create_table("roles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.String(160)))
    op.create_table("role_permissions", sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True), sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), primary_key=True))
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("full_name", sa.String(160), nullable=False), sa.Column("username", sa.String(80), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("gmail", sa.String(160), nullable=False, unique=True), sa.Column("corporate_email", sa.String(160)), sa.Column("phone", sa.String(50)), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)), sa.Column("main_area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False))
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table("user_roles", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True), sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True))
    op.create_table("user_permissions", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True), sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), primary_key=True))
    op.create_table("user_visible_areas", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True), sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), primary_key=True))
    op.create_table("persistent_login_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("selector", sa.String(64), nullable=False, unique=True), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("user_agent", sa.String(255)), sa.Column("ip_address", sa.String(80)))
    op.create_index("ix_persistent_login_tokens_user_id", "persistent_login_tokens", ["user_id"])
    op.create_index("ix_persistent_login_tokens_selector", "persistent_login_tokens", ["selector"])
    op.create_table("ticket_templates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(140), nullable=False), sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False), sa.Column("suggested_type", sa.String(60), nullable=False), sa.Column("suggested_subtype", sa.String(60), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("schema_json", sa.JSON()), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("tickets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("number", sa.String(20), nullable=False, unique=True), sa.Column("title", sa.String(180), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("ticket_type", sa.String(60), nullable=False), sa.Column("subtype", sa.String(60), nullable=False), sa.Column("creator_area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False), sa.Column("responsible_area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False), sa.Column("creator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("status", sa.String(60), nullable=False), sa.Column("priority", sa.String(30)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("tags", sa.String(255)), sa.Column("location", sa.String(160)), sa.Column("station", sa.String(160)), sa.Column("affected_equipment", sa.String(160)), sa.Column("template_id", sa.Integer(), sa.ForeignKey("ticket_templates.id")))
    op.create_index("ix_tickets_number", "tickets", ["number"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_table("ticket_comments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("comment", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("comment_type", sa.String(40)))
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])
    op.create_table("ticket_status_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False), sa.Column("old_status", sa.String(60)), sa.Column("new_status", sa.String(60), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("comment", sa.Text()))
    op.create_index("ix_ticket_status_history_ticket_id", "ticket_status_history", ["ticket_id"])
    op.create_table("ticket_transfers", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False), sa.Column("from_area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False), sa.Column("to_area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reason", sa.Text(), nullable=False))
    op.create_index("ix_ticket_transfers_ticket_id", "ticket_transfers", ["ticket_id"])
    op.create_table("ticket_attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id"), nullable=False), sa.Column("filename_original", sa.String(255), nullable=False), sa.Column("filename_storage", sa.String(255), nullable=False), sa.Column("path", sa.String(500), nullable=False), sa.Column("content_type", sa.String(120)), sa.Column("size", sa.Integer(), nullable=False), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
    op.create_table("audit_log", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("action", sa.String(120), nullable=False), sa.Column("entity_type", sa.String(80), nullable=False), sa.Column("entity_id", sa.String(80)), sa.Column("old_value", sa.Text()), sa.Column("new_value", sa.Text()), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("ip_address", sa.String(80)), sa.Column("user_agent", sa.String(255)))
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade():
    for table in ["audit_log", "ticket_attachments", "ticket_transfers", "ticket_status_history", "ticket_comments", "tickets", "ticket_templates", "persistent_login_tokens", "user_visible_areas", "user_permissions", "user_roles", "users", "role_permissions", "roles", "permissions", "areas"]:
        op.drop_table(table)
