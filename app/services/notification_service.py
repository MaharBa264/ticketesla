import logging

from flask import current_app, url_for

from app.models import User
from app.services.email_service import send_email
from app.time_utils import format_datetime_ar, now_utc

logger = logging.getLogger(__name__)

OPERATOR_PERMISSIONS = ("can_acknowledge_ticket", "can_resolve_ticket", "can_transfer_ticket")


def _corporate_email(user):
    return (user.corporate_email or "").strip() if user else ""


def _dedupe_emails(users):
    emails = []
    seen = set()
    for user in users:
        email = _corporate_email(user)
        key = email.lower()
        if email and key not in seen:
            seen.add(key)
            emails.append(email)
    return emails


def _operator_users_for_area(area_id):
    users = User.query.filter_by(active=True).all()
    result = []
    for user in users:
        can_operate = any(user.has_permission(permission) for permission in OPERATOR_PERMISSIONS)
        global_access = user.has_permission("can_view_all_tickets") or user.has_permission("can_manage_users")
        has_area = any(area.id == area_id for area in user.visible_areas)
        if _corporate_email(user) and can_operate and (global_access or has_area):
            result.append(user)
    return result


def _ticket_link(ticket):
    base_url = current_app.config.get("BASE_URL")
    if not base_url:
        return ""
    return f"{base_url}{url_for('tickets.detail', ticket_id=ticket.id)}"


def _ticket_body(ticket, title, extra_lines=None):
    lines = [
        title,
        "",
        f"Número: {ticket.number}",
        f"Título: {ticket.title}",
        f"Tipo: {ticket.ticket_type}",
        f"Subtipo: {ticket.subtype}",
        f"Estado: {ticket.status}",
        f"Área responsable: {ticket.responsible_area.name}",
        f"Creador: {ticket.creator.full_name}",
        f"Fecha/hora: {format_datetime_ar(now_utc())}",
    ]
    if extra_lines:
        lines.extend(["", *extra_lines])
    link = _ticket_link(ticket)
    if link:
        lines.extend(["", f"Link: {link}"])
    return "\n".join(lines)


class NotificationService:
    def notify_ticket_created(self, ticket):
        logger.info("Ticket creado: %s", ticket.number)
        recipients = [_corporate_email(ticket.assigned_user)] if ticket.assigned_user else []
        if not any(recipients):
            recipients = _dedupe_emails(_operator_users_for_area(ticket.responsible_area_id))
        subject = f"[Ticketesla] Nuevo ticket {ticket.number}"
        body = _ticket_body(ticket, "Se creó un nuevo ticket en Ticketesla.")
        send_email(recipients, subject, body)

    def notify_ticket_transferred(self, ticket, transfer):
        logger.info("Ticket %s derivado a %s", ticket.number, transfer.to_area.name)
        recipients = [_corporate_email(ticket.assigned_user)] if ticket.assigned_user else []
        if not any(recipients):
            recipients = _dedupe_emails(_operator_users_for_area(ticket.responsible_area_id))
        subject = f"[Ticketesla] Ticket derivado {ticket.number}"
        body = _ticket_body(
            ticket,
            "Un ticket fue derivado a otra área.",
            [f"Desde: {transfer.from_area.name}", f"Hacia: {transfer.to_area.name}", f"Motivo: {transfer.reason}"],
        )
        send_email(recipients, subject, body)

    def notify_ticket_due_soon(self, ticket):
        logger.info("Ticket próximo a vencer: %s", ticket.number)

    def notify_ticket_resolved(self, ticket):
        logger.info("Ticket resuelto: %s", ticket.number)
        recipient = _corporate_email(ticket.creator)
        subject = f"[Ticketesla] Ticket resuelto {ticket.number}"
        body = _ticket_body(ticket, "Tu ticket fue marcado como resuelto.")
        send_email([recipient] if recipient else [], subject, body)


notification_service = NotificationService()
