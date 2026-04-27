from datetime import timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Ticket
from app.services.permission_service import visible_area_ids
from app.time_utils import now_utc

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def index():
    area_ids = visible_area_ids(current_user)
    base = Ticket.query.filter(Ticket.responsible_area_id.in_(area_ids))
    now = now_utc()
    counts = {
        "Nuevos": base.filter_by(status="Nuevo").count(),
        "Reconocidos": base.filter_by(status="Reconocido").count(),
        "En curso": base.filter_by(status="En curso").count(),
        "Próximos a vencer": base.filter(Ticket.due_at != None, Ticket.due_at >= now, Ticket.due_at <= now + timedelta(days=3)).count(),
        "Vencidos": base.filter(Ticket.due_at != None, Ticket.due_at < now, Ticket.status.notin_(["Resuelto", "Cerrado"])).count(),
        "Resueltos recientes": base.filter(Ticket.status == "Resuelto", Ticket.updated_at >= now - timedelta(days=7)).count(),
    }
    tickets = base.order_by(Ticket.updated_at.desc()).limit(20).all()
    return render_template("dashboard/index.html", counts=counts, tickets=tickets)
