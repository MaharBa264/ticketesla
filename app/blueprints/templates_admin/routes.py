from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, TicketTemplate, TICKET_SUBTYPES, TICKET_TYPES
from app.services.audit_service import log_action
from app.services.permission_service import require_permission

templates_bp = Blueprint("templates_admin", __name__, url_prefix="/templates")


@templates_bp.route("/", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_templates")
def index():
    if request.method == "POST":
        template = TicketTemplate(
            name=request.form["name"].strip(),
            area_id=int(request.form["area_id"]),
            suggested_type=request.form["suggested_type"],
            suggested_subtype=request.form["suggested_subtype"],
            body=request.form["body"].strip(),
            active=bool(request.form.get("active")),
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.session.add(template)
        db.session.flush()
        log_action("template_created", "TicketTemplate", template.id)
        db.session.commit()
        flash("Plantilla creada.", "success")
        return redirect(url_for("templates_admin.index"))
    return render_template("templates_admin/index.html", templates=TicketTemplate.query.order_by(TicketTemplate.name).all(), areas=Area.query.order_by(Area.name).all(), types=TICKET_TYPES, subtypes=TICKET_SUBTYPES)


@templates_bp.post("/<int:template_id>/toggle")
@login_required
@require_permission("can_edit_templates")
def toggle(template_id):
    template = TicketTemplate.query.get_or_404(template_id)
    template.active = not template.active
    template.updated_by = current_user.id
    log_action("template_toggled", "TicketTemplate", template.id, new_value=str(template.active))
    db.session.commit()
    return redirect(url_for("templates_admin.index"))
