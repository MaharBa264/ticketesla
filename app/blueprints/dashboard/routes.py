from datetime import timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import ACTIVE_TICKET_STATUSES, Ticket
from app.services.permission_service import can_see_expanded_tickets, get_visible_ticket_query
from app.time_utils import now_utc

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def index():
    scope = "visible" if can_see_expanded_tickets(current_user) else "mine"
    base = get_visible_ticket_query(current_user, scope=scope)
    now = now_utc()
    counts = {
        "Nuevos": base.filter_by(status="Nuevo").count(),
        "Reconocidos": base.filter_by(status="Reconocido").count(),
        "En curso": base.filter_by(status="En curso").count(),
        "PrÃ³ximos a vencer": base.filter(Ticket.status.in_(ACTIVE_TICKET_STATUSES), Ticket.due_at != None, Ticket.due_at >= now, Ticket.due_at <= now + timedelta(days=3)).count(),
        "Vencidos": base.filter(Ticket.status.in_(ACTIVE_TICKET_STATUSES), Ticket.due_at != None, Ticket.due_at < now).count(),
        "Resueltos recientes": base.filter(Ticket.status == "Resuelto", Ticket.updated_at >= now - timedelta(days=7)).count(),
    }
    tickets = base.order_by(Ticket.updated_at.desc()).limit(20).all()
    return render_template("dashboard/index.html", counts=counts, tickets=tickets)

