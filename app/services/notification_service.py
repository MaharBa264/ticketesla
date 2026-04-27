import logging

logger = logging.getLogger(__name__)


class NotificationService:
    def notify_ticket_created(self, ticket):
        logger.info("Ticket creado: %s", ticket.number)

    def notify_ticket_transferred(self, ticket, transfer):
        logger.info("Ticket %s derivado a %s", ticket.number, transfer.to_area.name)

    def notify_ticket_due_soon(self, ticket):
        logger.info("Ticket próximo a vencer: %s", ticket.number)

    def notify_ticket_resolved(self, ticket):
        logger.info("Ticket resuelto: %s", ticket.number)


notification_service = NotificationService()
