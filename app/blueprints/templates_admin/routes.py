from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, TicketTemplate, TICKET_SUBTYPES, TICKET_TYPES
from app.services.audit_service import log_action
from app.services.permission_service import require_permission

templates_bp = Blueprint("templates_admin", __name__, url_prefix="/templates")


def _template_from_form(template=None):
    """Crea o actualiza una plantilla desde un formulario HTML."""
    if template is None:
        template = TicketTemplate(created_by=current_user.id)

    template.name = request.form.get("name", "").strip()
    template.area_id = int(request.form.get("area_id"))
    template.suggested_type = request.form.get("suggested_type")
    template.suggested_subtype = request.form.get("suggested_subtype")
    template.body = request.form.get("body", "").strip()
    template.active = bool(request.form.get("active"))
    template.updated_by = current_user.id
    return template


def _validate_template_form():
    errors = []
    if not request.form.get("name", "").strip():
        errors.append("La plantilla necesita un nombre.")
    if not request.form.get("body", "").strip():
        errors.append("La plantilla necesita un texto base.")
    if request.form.get("suggested_type") not in TICKET_TYPES:
        errors.append("El tipo sugerido no es válido.")
    if request.form.get("suggested_subtype") not in TICKET_SUBTYPES:
        errors.append("El subtipo sugerido no es válido.")
    return errors


@templates_bp.route("/", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_templates")
def index():
    areas = Area.query.order_by(Area.name).all()

    if request.method == "POST":
        errors = _validate_template_form()
        if errors:
            for error in errors:
                flash(error, "warning")
        else:
            template = _template_from_form()
            db.session.add(template)
            db.session.flush()
            log_action("template_created", "TicketTemplate", template.id)
            db.session.commit()
            flash("Plantilla creada.", "success")
            return redirect(url_for("templates_admin.index"))

    templates = (
        TicketTemplate.query
        .join(Area, TicketTemplate.area_id == Area.id)
        .order_by(Area.name, TicketTemplate.suggested_type, TicketTemplate.name)
        .all()
    )
    return render_template(
        "templates_admin/index.html",
        templates=templates,
        areas=areas,
        types=TICKET_TYPES,
        subtypes=TICKET_SUBTYPES,
    )


@templates_bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_templates")
def edit(template_id):
    template = TicketTemplate.query.get_or_404(template_id)
    areas = Area.query.order_by(Area.name).all()

    if request.method == "POST":
        errors = _validate_template_form()
        if errors:
            for error in errors:
                flash(error, "warning")
        else:
            old_value = f"{template.name}|{template.area_id}|{template.suggested_type}|{template.suggested_subtype}|{template.active}"
            _template_from_form(template)
            log_action(
                "template_updated",
                "TicketTemplate",
                template.id,
                old_value=old_value,
                new_value=f"{template.name}|{template.area_id}|{template.suggested_type}|{template.suggested_subtype}|{template.active}",
            )
            db.session.commit()
            flash("Plantilla actualizada.", "success")
            return redirect(url_for("templates_admin.index"))

    return render_template(
        "templates_admin/edit.html",
        template=template,
        areas=areas,
        types=TICKET_TYPES,
        subtypes=TICKET_SUBTYPES,
    )


@templates_bp.post("/<int:template_id>/toggle")
@login_required
@require_permission("can_edit_templates")
def toggle(template_id):
    template = TicketTemplate.query.get_or_404(template_id)
    template.active = not template.active
    template.updated_by = current_user.id
    log_action("template_toggled", "TicketTemplate", template.id, new_value=str(template.active))
    db.session.commit()
    flash("Estado de plantilla actualizado.", "success")
    return redirect(url_for("templates_admin.index"))
