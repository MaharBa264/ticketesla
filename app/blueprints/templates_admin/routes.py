import re
import unicodedata

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, TicketTemplate, TICKET_SUBTYPES, TICKET_TYPES
from app.services.audit_service import log_action
from app.services.permission_service import require_permission


templates_bp = Blueprint("templates_admin", __name__, url_prefix="/templates")

FIELD_TYPES = (
    ("text", "Texto corto"),
    ("textarea", "Texto largo"),
    ("number", "Número"),
    ("date", "Fecha"),
    ("datetime-local", "Fecha y hora"),
    ("select", "Lista desplegable"),
    ("checkbox", "Sí / No"),
)
FIELD_TYPE_KEYS = {key for key, _ in FIELD_TYPES}


def _slugify(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or "campo"


def _unique_key(base_key, used):
    key = base_key
    counter = 2
    while key in used:
        key = f"{base_key}_{counter}"
        counter += 1
    used.add(key)
    return key


def parse_template_schema(form):
    """Convierte los campos dinámicos del formulario en un schema JSON simple."""
    labels = form.getlist("field_label[]")
    keys = form.getlist("field_key[]")
    types = form.getlist("field_type[]")
    placeholders = form.getlist("field_placeholder[]")
    helps = form.getlist("field_help[]")
    options_list = form.getlist("field_options[]")
    required_indexes = set(form.getlist("field_required[]"))

    fields = []
    used_keys = set()
    for idx, raw_label in enumerate(labels):
        label = (raw_label or "").strip()
        if not label:
            continue
        raw_key = keys[idx] if idx < len(keys) else ""
        field_type = types[idx] if idx < len(types) else "text"
        if field_type not in FIELD_TYPE_KEYS:
            field_type = "text"
        key = _unique_key(_slugify(raw_key or label), used_keys)
        options_raw = options_list[idx] if idx < len(options_list) else ""
        options = [item.strip() for item in re.split(r"[\n,;]+", options_raw) if item.strip()]
        fields.append(
            {
                "key": key,
                "label": label,
                "type": field_type,
                "required": str(idx) in required_indexes,
                "placeholder": (placeholders[idx] if idx < len(placeholders) else "").strip(),
                "help": (helps[idx] if idx < len(helps) else "").strip(),
                "options": options,
            }
        )
    return {"version": 1, "fields": fields}


@templates_bp.route("/", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_templates")
def index():
    if request.method == "POST":
        schema = parse_template_schema(request.form)
        template = TicketTemplate(
            name=request.form["name"].strip(),
            area_id=int(request.form["area_id"]),
            suggested_type=request.form["suggested_type"],
            suggested_subtype=request.form["suggested_subtype"],
            body=request.form.get("body", "").strip(),
            schema_json=schema,
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

    return render_template(
        "templates_admin/index.html",
        templates=TicketTemplate.query.order_by(TicketTemplate.active.desc(), TicketTemplate.name).all(),
        areas=Area.query.order_by(Area.name).all(),
        types=TICKET_TYPES,
        subtypes=TICKET_SUBTYPES,
        field_types=FIELD_TYPES,
    )


@templates_bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_templates")
def edit(template_id):
    template = TicketTemplate.query.get_or_404(template_id)
    if request.method == "POST":
        old_value = f"{template.name}|{template.area_id}|{template.suggested_type}|{template.active}"
        template.name = request.form["name"].strip()
        template.area_id = int(request.form["area_id"])
        template.suggested_type = request.form["suggested_type"]
        template.suggested_subtype = request.form["suggested_subtype"]
        template.body = request.form.get("body", "").strip()
        template.schema_json = parse_template_schema(request.form)
        template.active = bool(request.form.get("active"))
        template.updated_by = current_user.id
        log_action(
            "template_edited",
            "TicketTemplate",
            template.id,
            old_value=old_value,
            new_value=f"{template.name}|{template.area_id}|{template.suggested_type}|{template.active}",
        )
        db.session.commit()
        flash("Plantilla actualizada.", "success")
        return redirect(url_for("templates_admin.index"))

    return render_template(
        "templates_admin/edit.html",
        template=template,
        areas=Area.query.order_by(Area.name).all(),
        types=TICKET_TYPES,
        subtypes=TICKET_SUBTYPES,
        field_types=FIELD_TYPES,
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
    return redirect(url_for("templates_admin.index"))
