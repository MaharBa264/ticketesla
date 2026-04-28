import logging

from flask import current_app, url_for

from app.models import User
from app.services.email_service import send_email
from app.time_utils import format_datetime_ar

logger = logging.getLogger(__name__)

OPERATIVE_PERMISSIONS = {
    "can_acknowledge_ticket",
    "can_resolve_ticket",
    "can_transfer_ticket",
    "can_edit_ticket",
}


class NotificationService:
    def _base_url(self):
        return (current_app.config.get("BASE_URL") or "").rstrip("/")

    def _ticket_url(self, ticket):
        base_url = self._base_url()
        if not base_url:
            return None
        return f"{base_url}{url_for('tickets.detail', ticket_id=ticket.id)}"

    def _user_is_operator_for_area(self, user, area_id):
        if not user or not user.active or not user.corporate_email:
            return False
        if not (user.main_area_id == area_id or user.can_view_area(area_id)):
            return False
        return any(user.has_permission(permission) for permission in OPERATIVE_PERMISSIONS)

    def _area_operator_emails(self, area_id):
        users = User.query.filter_by(active=True).all()
        emails = []
        for user in users:
            if self._user_is_operator_for_area(user, area_id):
                emails.append(user.corporate_email)
        return self._unique(emails)

    def _assigned_or_area_emails(self, ticket):
        if ticket.assigned_user and ticket.assigned_user.active and ticket.assigned_user.corporate_email:
            return [ticket.assigned_user.corporate_email]
        return self._area_operator_emails(ticket.responsible_area_id)

    def _unique(self, emails):
        seen = set()
        result = []
        for email in emails or []:
            email = (email or "").strip()
            if not email:
                continue
            key = email.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(email)
        return result

    def _ticket_body(self, ticket, title, actor=None, extra_lines=None):
        lines = [
            title,
            "",
            f"Número: {ticket.number}",
            f"Título: {ticket.title}",
            f"Tipo: {ticket.ticket_type}",
            f"Subtipo: {ticket.subtype}",
            f"Estado: {ticket.status}",
            f"Área responsable: {ticket.responsible_area.name if ticket.responsible_area else '-'}",
            f"Creador: {ticket.creator.full_name if ticket.creator else '-'}",
            f"Fecha/hora: {format_datetime_ar(ticket.updated_at or ticket.created_at)}",
        ]
        if actor:
            lines.append(f"Usuario: {actor.full_name}")
        if extra_lines:
            lines.extend(extra_lines)
        url = self._ticket_url(ticket)
        if url:
            lines.extend(["", f"Ver ticket: {url}"])
        return "\n".join(lines)

    def _send(self, subject, body, recipients):
        return send_email(subject, body, recipients)

    def notify_ticket_created(self, ticket):
        logger.info("Ticket creado: %s", ticket.number)
        subject = f"[Ticketesla] Nuevo ticket {ticket.number}"
        body = self._ticket_body(ticket, "Se creó un nuevo ticket.")
        return self._send(subject, body, self._assigned_or_area_emails(ticket))

    def notify_ticket_transferred(self, ticket, transfer):
        logger.info("Ticket %s derivado a %s", ticket.number, transfer.to_area.name)
        subject = f"[Ticketesla] Ticket derivado {ticket.number}"
        body = self._ticket_body(
            ticket,
            "Un ticket fue derivado a tu área.",
            actor=transfer.user,
            extra_lines=[
                f"Área anterior: {transfer.from_area.name}",
                f"Área destino: {transfer.to_area.name}",
                f"Motivo: {transfer.reason}",
            ],
        )
        return self._send(subject, body, self._area_operator_emails(transfer.to_area_id))

    def notify_ticket_due_soon(self, ticket):
        logger.info("Ticket próximo a vencer: %s", ticket.number)

    def notify_ticket_resolved(self, ticket):
        logger.info("Ticket resuelto: %s", ticket.number)
        subject = f"[Ticketesla] Ticket resuelto {ticket.number}"
        body = self._ticket_body(ticket, "Tu ticket fue marcado como resuelto.")
        recipients = []
        if ticket.creator and ticket.creator.corporate_email:
            recipients.append(ticket.creator.corporate_email)
        return self._send(subject, body, recipients)

    def notify_ticket_reopened(self, ticket, actor=None):
        logger.info("Ticket reabierto: %s", ticket.number)
        subject = f"[Ticketesla] Ticket reabierto {ticket.number}"
        body = self._ticket_body(ticket, "Un ticket fue reabierto y requiere atención nuevamente.", actor=actor)
        return self._send(subject, body, self._area_operator_emails(ticket.responsible_area_id))


notification_service = NotificationService()
