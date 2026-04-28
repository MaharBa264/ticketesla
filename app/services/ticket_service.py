import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Area, Ticket, TicketAttachment, TicketComment, TicketStatusHistory, TicketTemplate, TicketTransfer
from app.services.audit_service import log_action
from app.services.notification_service import notification_service
from app.services.permission_service import can_operate_ticket
from app.time_utils import LOCAL_TZ, now_utc

DEFAULT_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".xlsx", ".docx", ".zip"}


def candidate_uploads(files):
    return [file for file in files if isinstance(file, FileStorage) and file.filename]


def allowed_upload_extensions():
    raw = current_app.config.get("ALLOWED_UPLOAD_EXTENSIONS") or ""
    if not raw:
        return DEFAULT_ALLOWED_EXTENSIONS
    return {f".{item.strip().lower().lstrip('.')}" for item in raw.split(",") if item.strip()}


def file_size(file):
    stream = file.stream
    position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size


def validate_attachment(file):
    if not isinstance(file, FileStorage) or not file.filename:
        return None, "Archivo vacío o sin nombre."
    original = secure_filename(file.filename)
    if not original:
        return None, "Archivo vacío o sin nombre."
    suffix = Path(original).suffix.lower()
    if suffix not in allowed_upload_extensions():
        return None, f"Formato no permitido: {suffix or 'sin extensión'}."
    size = file_size(file)
    if size <= 0:
        return None, "Archivo vacío."
    max_size = current_app.config.get("MAX_CONTENT_LENGTH")
    if max_size and size > max_size:
        return None, "El archivo supera el tamaño máximo permitido."
    return {"original": original, "suffix": suffix, "size": size}, None


def form_has_meaningful_free_content(form):
    fields = [form.get("description"), form.get("location"), form.get("affected_equipment")]
    return any((value or "").strip() for value in fields)


def structured_form_has_any_answer(template, form):
    if not template or not template.schema_json:
        return False
    for field in template.schema_json.get("fields") or []:
        key = field.get("key")
        if not key:
            continue
        name = f"structured_{key}"
        if field.get("type") == "checkbox":
            if form.get(name):
                return True
        elif (form.get(name) or "").strip():
            return True
    return False


def validate_ticket_minimum_content(form, files):
    """Evita tickets vacíos cuando el usuario no usa plantilla ni carga datos reales."""
    template = get_selected_template(form)
    has_template = template is not None
    has_free_content = form_has_meaningful_free_content(form)
    has_structured_answer = structured_form_has_any_answer(template, form)
    has_attachments = bool(candidate_uploads(files))

    if not (has_template or has_free_content or has_structured_answer or has_attachments):
        raise ValueError(
            "Para crear un ticket sin plantilla, completá al menos Observaciones, "
            "Ubicación, Equipo afectado o adjuntá un archivo."
        )


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
        sections.append(("Observaciones", "Sin observaciones adicionales."))
    return "\n\n".join(f"{title}:\n{body}" for title, body in sections)


def build_title(template, structured_data, free_description, ticket_type):
    parts = []
    if template and template.name:
        parts.append(template.name)
    else:
        parts.append(ticket_type or "Ticket")
    if structured_data and structured_data.get("fields"):
        for item in structured_data["fields"]:
            value = item.get("value")
            if item.get("type") == "checkbox" or value in (None, ""):
                continue
            parts.append(str(value).replace("\n", " ").strip())
            break
    elif free_description:
        parts.append(str(free_description).replace("\n", " ").strip()[:60])
    title = " - ".join(part for part in parts if part)
    return (title[:177] + "...") if len(title) > 180 else title


def resolve_responsible_area_id(ticket_type, form, user):
    if ticket_type == "Registro de cambio":
        return user.main_area_id
    value = form.get("responsible_area_id")
    return int(value) if value else user.main_area_id


def create_ticket(form, user):
    ticket_type = form.get("ticket_type")
    status = "Resuelto" if ticket_type == "Registro de cambio" else "Nuevo"
    template = get_selected_template(form)
    structured_data = collect_structured_data(template, form)
    description = build_description(template, structured_data, form.get("description"))
    title = build_title(template, structured_data, form.get("description"), ticket_type)
    ticket = Ticket(
        number=next_ticket_number(), title=title, description=description,
        ticket_type=ticket_type, subtype=form.get("subtype"), creator_area_id=user.main_area_id,
        responsible_area_id=resolve_responsible_area_id(ticket_type, form, user), creator_user_id=user.id,
        status=status, priority=None, due_at=parse_local_datetime(form.get("due_at")) if ticket_type == "Solicitud de intervención" else None,
        closed_at=None, tags=None,
        location=form.get("location") or None, station=None,
        affected_equipment=form.get("affected_equipment") or None,
        template_id=template.id if template else None, structured_data=structured_data,
    )
    db.session.add(ticket)
    db.session.flush()
    db.session.add(TicketStatusHistory(ticket=ticket, old_status=None, new_status=status, user_id=user.id))
    log_action("ticket_created", "Ticket", ticket.id, new_value=ticket.number, user=user)
    notification_service.notify_ticket_created(ticket)
    return ticket



def allowed_status_actions(ticket, user):
    """Devuelve los próximos estados válidos para el usuario y el estado actual del ticket."""
    actions = []

    if ticket.ticket_type == "Registro de cambio":
        if ticket.status != "Cerrado" and can_operate_ticket(ticket, user, "can_resolve_ticket"):
            actions.append(("Cerrado", "Cerrar"))
        if ticket.status == "Cerrado" and can_operate_ticket(ticket, user, "can_reopen_ticket"):
            actions.append(("Reabierto", "Reabrir"))
        return actions

    status = ticket.status
    if status in ("Nuevo", "Derivado", "Reabierto") and can_operate_ticket(ticket, user, "can_acknowledge_ticket"):
        actions.append(("Reconocido", "Reconocer"))
    if status in ("Reconocido", "Derivado", "Pendiente de tercero", "Reabierto") and can_operate_ticket(ticket, user, "can_resolve_ticket"):
        actions.append(("En curso", "Marcar en curso"))
    if status in ("Reconocido", "En curso") and can_operate_ticket(ticket, user, "can_resolve_ticket"):
        actions.append(("Pendiente de tercero", "Pendiente de tercero"))
    if status in ("Reconocido", "En curso", "Pendiente de tercero", "Derivado", "Reabierto") and can_operate_ticket(ticket, user, "can_resolve_ticket"):
        actions.append(("Resuelto", "Resolver"))
    if status == "Resuelto" and can_operate_ticket(ticket, user, "can_resolve_ticket"):
        actions.append(("Cerrado", "Cerrar"))
    if status == "Cerrado" and can_operate_ticket(ticket, user, "can_reopen_ticket"):
        actions.append(("Reabierto", "Reabrir"))
    return actions


def is_status_action_allowed(ticket, new_status, user):
    return any(status == new_status for status, _label in allowed_status_actions(ticket, user))

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
    extra_hand_granted = False
    if old_status != new_status and new_status in ("Resuelto", "Cerrado"):
        try:
            from app.services.game_service import grant_extra_hand_for_ticket_action

            extra_hand_granted = grant_extra_hand_for_ticket_action(user, ticket, new_status)
        except Exception:
            current_app.logger.exception("No se pudo otorgar mano extra por ticket %s", ticket.number)
    if new_status == "Resuelto":
        notification_service.notify_ticket_resolved(ticket)
    return extra_hand_granted


def transfer_ticket(ticket, to_area_id, reason, user):
    if not reason or not reason.strip():
        raise ValueError("La explicación de la derivación es obligatoria.")
    if ticket.ticket_type != "Solicitud de intervención":
        raise ValueError("Solo las solicitudes de intervención pueden derivarse.")
    if ticket.status in ("Resuelto", "Cerrado"):
        raise ValueError("No se puede derivar un ticket resuelto o cerrado.")
    try:
        destination_id = int(to_area_id)
    except (TypeError, ValueError):
        raise ValueError("Seleccioná un área destino válida.") from None
    if destination_id == ticket.responsible_area_id:
        raise ValueError("El área destino debe ser distinta al área responsable actual.")
    destination = Area.query.filter_by(id=destination_id, active=True).first()
    if not destination:
        raise ValueError("Seleccioná un área destino válida.")
    old_area = ticket.responsible_area_id
    old_area_obj = ticket.responsible_area
    old_status = ticket.status
    transfer = TicketTransfer(ticket=ticket, from_area=old_area_obj, to_area=destination, user_id=user.id, reason=reason.strip())
    ticket.responsible_area_id = destination.id
    ticket.status = "Derivado"
    ticket.updated_at = now_utc()
    db.session.add(transfer)
    db.session.add(TicketStatusHistory(ticket=ticket, old_status=old_status, new_status="Derivado", user_id=user.id, comment=reason.strip()))
    log_action("ticket_transferred", "Ticket", ticket.id, old_value=str(old_area), new_value=str(destination.id), user=user)
    notification_service.notify_ticket_transferred(ticket, transfer)
    return transfer


def add_comment(ticket, user, comment, comment_type=None):
    item = TicketComment(ticket=ticket, user_id=user.id, comment=comment.strip(), comment_type=comment_type)
    ticket.updated_at = now_utc()
    db.session.add(item)
    log_action("ticket_comment_added", "Ticket", ticket.id, new_value=comment[:200], user=user)
    return item


def storage_root():
    root = Path(current_app.config["STORAGE_PATH"])
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except PermissionError:
        is_dev = current_app.config.get("RELEASE_VERSION") == "dev" or os.getenv("FLASK_ENV", "").lower() == "development"
        if not is_dev:
            raise
        fallback = Path(current_app.root_path).parent / "storage"
        fallback.mkdir(parents=True, exist_ok=True)
        current_app.logger.warning("STORAGE_PATH %s no es escribible; usando %s para DEV", root, fallback)
        return fallback


def get_attachment_storage_path(ticket):
    return storage_root() / "attachments" / ticket.number


def save_attachments(ticket, files, user):
    valid_files = candidate_uploads(files)
    if not valid_files:
        return {"saved": [], "errors": []}
    saved = []
    errors = []
    try:
        base = get_attachment_storage_path(ticket)
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        current_app.logger.exception("No se pudo preparar STORAGE_PATH para adjuntos del ticket %s", ticket.number)
        return {"saved": [], "errors": [str(exc)]}
    for file in valid_files:
        metadata, error = validate_attachment(file)
        if error:
            errors.append(f"{file.filename}: {error}")
            current_app.logger.warning("Adjunto rechazado en ticket %s: %s", ticket.number, error)
            continue
        original = metadata["original"]
        suffix = metadata["suffix"]
        storage_name = f"{uuid4().hex}{suffix}"
        path = base / storage_name
        try:
            file.save(path)
            size = path.stat().st_size
            if size <= 0:
                path.unlink(missing_ok=True)
                errors.append(f"{file.filename}: Archivo vacío.")
                continue
            attachment = TicketAttachment(
                ticket=ticket,
                filename_original=original,
                filename_storage=storage_name,
                path=str(path),
                content_type=file.content_type,
                size=size,
                uploaded_by=user.id,
            )
            db.session.add(attachment)
            saved.append(attachment)
        except OSError as exc:
            current_app.logger.exception("No se pudo guardar adjunto %s en ticket %s", original, ticket.number)
            errors.append(f"{file.filename}: {exc}")
    if saved:
        log_action("ticket_attachments_added", "Ticket", ticket.id, new_value=str(len(saved)), user=user)
    return {"saved": saved, "errors": errors}
