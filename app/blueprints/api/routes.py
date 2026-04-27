from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import Ticket, User
from app.services.permission_service import can_operate_ticket, can_view_ticket, get_visible_ticket_query
from app.services.ticket_service import add_comment, change_status, create_ticket, transfer_ticket
from app.time_utils import format_datetime_ar, now_utc

api_bp = Blueprint("api", __name__)


def ticket_payload(ticket):
    return {
        "id": ticket.id,
        "number": ticket.number,
        "title": ticket.title,
        "description": ticket.description,
        "ticket_type": ticket.ticket_type,
        "subtype": ticket.subtype,
        "status": ticket.status,
        "responsible_area": ticket.responsible_area.name,
        "creator_area": ticket.creator_area.name,
        "created_at": ticket.created_at.isoformat(),
        "created_at_display": format_datetime_ar(ticket.created_at),
        "updated_at": ticket.updated_at.isoformat(),
        "due_at": ticket.due_at.isoformat() if ticket.due_at else None,
    }


@api_bp.post("/auth/login")
def login():
    data = request.get_json() or {}
    user = User.query.filter_by(username=data.get("username", "")).first()
    if not user or not user.active or not user.check_password(data.get("password", "")):
        return jsonify({"error": "Credenciales inválidas"}), 401
    user.last_login_at = now_utc()
    login_user(user)
    db.session.commit()
    return jsonify({"ok": True, "user": {"id": user.id, "username": user.username, "full_name": user.full_name}})


@api_bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})


@api_bp.get("/me")
@login_required
def me():
    return jsonify({"id": current_user.id, "username": current_user.username, "full_name": current_user.full_name, "area": current_user.main_area.name})


@api_bp.get("/tickets")
@login_required
def tickets():
    rows = get_visible_ticket_query(current_user).order_by(Ticket.updated_at.desc()).limit(200).all()
    return jsonify([ticket_payload(ticket) for ticket in rows])


@api_bp.post("/tickets")
@login_required
def create_ticket_api():
    if not current_user.has_permission("can_create_ticket"):
        abort(403)
    ticket = create_ticket(request.get_json() or {}, current_user)
    db.session.commit()
    return jsonify(ticket_payload(ticket)), 201


@api_bp.get("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_view_ticket(ticket, current_user):
        abort(403)
    return jsonify(ticket_payload(ticket))


@api_bp.post("/tickets/<int:ticket_id>/comments")
@login_required
def ticket_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_view_ticket(ticket, current_user):
        abort(403)
    add_comment(ticket, current_user, (request.get_json() or {}).get("comment", ""))
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.post("/tickets/<int:ticket_id>/acknowledge")
@login_required
def ticket_acknowledge(ticket_id):
    if not current_user.has_permission("can_acknowledge_ticket"):
        abort(403)
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_operate_ticket(ticket, current_user, "can_acknowledge_ticket"):
        abort(403)
    change_status(ticket, "Reconocido", current_user)
    db.session.commit()
    return jsonify(ticket_payload(ticket))


@api_bp.post("/tickets/<int:ticket_id>/resolve")
@login_required
def ticket_resolve(ticket_id):
    if not current_user.has_permission("can_resolve_ticket"):
        abort(403)
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_operate_ticket(ticket, current_user, "can_resolve_ticket"):
        abort(403)
    change_status(ticket, "Resuelto", current_user, (request.get_json() or {}).get("comment"))
    db.session.commit()
    return jsonify(ticket_payload(ticket))


@api_bp.post("/tickets/<int:ticket_id>/transfer")
@login_required
def ticket_transfer(ticket_id):
    if not current_user.has_permission("can_transfer_ticket"):
        abort(403)
    data = request.get_json() or {}
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_operate_ticket(ticket, current_user, "can_transfer_ticket"):
        abort(403)
    transfer_ticket(ticket, data.get("to_area_id"), data.get("reason"), current_user)
    db.session.commit()
    return jsonify(ticket_payload(ticket))
