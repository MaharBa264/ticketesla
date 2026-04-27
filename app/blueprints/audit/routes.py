from flask import Blueprint, render_template
from flask_login import login_required

from app.models import AuditLog
from app.services.permission_service import require_permission

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.get("/")
@login_required
@require_permission("can_view_audit_log")
def index():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(300).all()
    return render_template("audit/index.html", logs=logs)
