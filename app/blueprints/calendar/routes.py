from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import Area, Ticket, TICKET_STATUSES
from app.services.permission_service import visible_area_ids
from app.time_utils import utc_to_local

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.get("/")
@login_required
def index():
    return render_template("calendar/index.html", areas=Area.query.order_by(Area.name).all(), statuses=TICKET_STATUSES)


@calendar_bp.get("/events")
@login_required
def events():
    query = Ticket.query.filter(Ticket.due_at != None, Ticket.responsible_area_id.in_(visible_area_ids(current_user)))
    if request.args.get("area_id"):
        query = query.filter_by(responsible_area_id=int(request.args["area_id"]))
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"])
    return jsonify([
        {
            "id": ticket.id,
            "title": f"{ticket.number} - {ticket.title}",
            "start": utc_to_local(ticket.due_at).isoformat(),
            "url": f"/tickets/{ticket.id}",
        }
        for ticket in query.all()
    ])
