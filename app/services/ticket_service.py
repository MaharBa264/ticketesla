from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Ticket, TicketAttachment, TicketComment, TicketStatusHistory, TicketTemplate, TicketTransfer
from app.services.audit_service import log_action
from app.services.notification_service import notification_service
from app.time_utils import LOCAL_TZ, now_utc

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".xlsx", ".docx", ".zip"}


def next_ticket_number():
    last = Ticket.query.order_by(Ticket.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f"TES-{next_id:06d}"


def parse_local_datetime(value):
    if not value:
        return None
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    return parsed.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def get_selected_template(form):
    template_id = form.get("template_id")
    return TicketTemplate.query.get(int(template_id)) if template_id else None


def collect_structured_data(template, form):
    if not template or not template.schema_json:
        return None
    fields = template.schema_json.get("fields") or []
    if not fields:
        return None
    answers = []
    for field in fields:
        key = field.get("key")
        label = field.get("label") or key
        field_type = field.get("type") or "text"
        name = f"structured_{key}"
        value = bool(form.get(name)) if field_type == "checkbox" else (form.get(name) or "").strip()
        if field.get("required") and (value is False or value == ""):
            raise ValueError(f"Completá el campo obligatorio: {label}.")
        answers.append({"key": key, "label": label, "type": field_type, "value": value})
    return {"template_id": template.id, "template_name": template.name, "fields": answers}


def build_description(template, structured_data, free_description):
    free_description = (free_description or "").strip()
    sections = []
    if template and template.body and template.body.strip():
        sections.append(("Texto guía de la plantilla", template.body.strip()))
    if structured_data and structured_data.get("fields"):
        lines = []
        for item in structured_data["fields"]:
            value = item.get("value")
            if item.get("type") == "checkbox":
                value = "Sí" if value else "No"
            if value in (None, ""):
                value = "-"
            lines.append(f"{item.get('label')}: {value}")
        sections.append(("Datos cargados", "\n".join(lines)))
    if free_description:
        sections.append(("Observaciones", free_description))
    if not sections:
        raise ValueError("La descripción es obligatoria si no se usa una plantilla con campos estructurados.")
    return "\n\n".join(f"{title}:\n{body}" for title, body in sections)


def create_ticket(form, user):
    ticket_type = form.get("ticket_type")
    status = "Cerrado" if ticket_type == "Registro de cambio" else "Nuevo"
    template = get_selected_template(form)
    structured_data = collect_structured_data(template, form)
    description = build_description(template, structured_data, form.get("description"))
    ticket = Ticket(
        number=next_ticket_number(), title=form.get("title", "").strip(), description=description,
        ticket_type=ticket_type, subtype=form.get("subtype"), creator_area_id=user.main_area_id,
        responsible_area_id=int(form.get("responsible_area_id")), creator_user_id=user.id,
        status=status, priority=form.get("priority") or None, due_at=parse_local_datetime(form.get("due_at")),
        closed_at=now_utc() if status == "Cerrado" else None, tags=form.get("tags") or None,
        location=form.get("location") or None, station=form.get("station") or None,
        affected_equipment=form.get("affected_equipment") or None,
        template_id=template.id if template else None, structured_data=structured_data,
    )
    db.session.add(ticket)
    db.session.flush()
    db.session.add(TicketStatusHistory(ticket=ticket, old_status=None, new_status=status, user_id=user.id))
    log_action("ticket_created", "Ticket", ticket.id, new_value=ticket.number, user=user)
    notification_service.notify_ticket_created(ticket)
    return ticket


def change_status(ticket, new_status, user, comment=None):
    old_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = now_utc()
    if new_status == "Cerrado":
        ticket.closed_at = now_utc()
    if new_status == "Reabierto":
        ticket.closed_at = None
    db.session.add(TicketStatusHistory(ticket=ticket, old_status=old_status, new_status=new_status, user_id=user.id, comment=comment))
    log_action("ticket_status_changed", "Ticket", ticket.id, old_value=old_status, new_value=new_status, user=user)
    if new_status == "Resuelto":
        notification_service.notify_ticket_resolved(ticket)


def transfer_ticket(ticket, to_area_id, reason, user):
    if not reason or not reason.strip():
        raise ValueError("La explicación de la derivación es obligatoria.")
    old_area = ticket.responsible_area_id
    old_status = ticket.status
    transfer = TicketTransfer(ticket=ticket, from_area_id=old_area, to_area_id=int(to_area_id), user_id=user.id, reason=reason.strip())
    ticket.responsible_area_id = int(to_area_id)
    ticket.status = "Derivado"
    ticket.updated_at = now_utc()
    db.session.add(transfer)
    db.session.add(TicketStatusHistory(ticket=ticket, old_status=old_status, new_status="Derivado", user_id=user.id, comment=reason))
    log_action("ticket_transferred", "Ticket", ticket.id, old_value=str(old_area), new_value=str(to_area_id), user=user)
    notification_service.notify_ticket_transferred(ticket, transfer)
    return transfer


def add_comment(ticket, user, comment, comment_type=None):
    item = TicketComment(ticket=ticket, user_id=user.id, comment=comment.strip(), comment_type=comment_type)
    ticket.updated_at = now_utc()
    db.session.add(item)
    log_action("ticket_comment_added", "Ticket", ticket.id, new_value=comment[:200], user=user)
    return item


def save_attachments(ticket, files, user):
    saved = []
    base = Path(current_app.config["STORAGE_PATH"]) / "attachments" / ticket.number
    base.mkdir(parents=True, exist_ok=True)
    for file in files:
        if not isinstance(file, FileStorage) or not file.filename:
            continue
        original = secure_filename(file.filename)
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            continue
        storage_name = f"{uuid4().hex}{suffix}"
        path = base / storage_name
        file.save(path)
        attachment = TicketAttachment(ticket=ticket, filename_original=original, filename_storage=storage_name, path=str(path), content_type=file.content_type, size=path.stat().st_size, uploaded_by=user.id)
        db.session.add(attachment)
        saved.append(attachment)
    if saved:
        log_action("ticket_attachments_added", "Ticket", ticket.id, new_value=str(len(saved)), user=user)
    return saved
