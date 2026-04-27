from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, Ticket, TicketAttachment, TicketTemplate, TICKET_STATUSES, TICKET_SUBTYPES, TICKET_TYPES, PRIORITIES
from app.services.permission_service import require_permission, visible_area_ids
from app.services.audit_service import log_action
from app.services.ticket_service import add_comment, change_status, create_ticket, save_attachments, transfer_ticket

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def get_visible_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not current_user.can_view_area(ticket.responsible_area_id) and ticket.creator_user_id != current_user.id:
        abort(403)
    return ticket


@tickets_bp.get("/")
@login_required
def index():
    query = Ticket.query
    if request.args.get("mine"):
        query = query.filter_by(creator_user_id=current_user.id)
    else:
        query = query.filter(Ticket.responsible_area_id.in_(visible_area_ids(current_user)))
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"])
    if request.args.get("ticket_type"):
        query = query.filter_by(ticket_type=request.args["ticket_type"])
    if request.args.get("area_id"):
        query = query.filter_by(responsible_area_id=int(request.args["area_id"]))
    text = request.args.get("q", "").strip()
    if text:
        like = f"%{text}%"
        query = query.filter((Ticket.title.ilike(like)) | (Ticket.description.ilike(like)) | (Ticket.number.ilike(like)) | (Ticket.station.ilike(like)) | (Ticket.affected_equipment.ilike(like)) | (Ticket.location.ilike(like)) | (Ticket.tags.ilike(like)))
    tickets = query.order_by(Ticket.updated_at.desc()).limit(200).all()
    return render_template("tickets/index.html", tickets=tickets, statuses=TICKET_STATUSES, types=TICKET_TYPES, areas=Area.query.order_by(Area.name).all())


@tickets_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("can_create_ticket")
def create():
    areas = Area.query.filter_by(active=True).order_by(Area.name).all()
    templates = TicketTemplate.query.filter_by(active=True).order_by(TicketTemplate.name).all()
    if request.method == "POST":
        ticket = create_ticket(request.form, current_user)
        save_attachments(ticket, request.files.getlist("attachments"), current_user)
        db.session.commit()
        flash(f"Ticket {ticket.number} creado.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))
    return render_template("tickets/create.html", areas=areas, templates=templates, types=TICKET_TYPES, subtypes=TICKET_SUBTYPES, priorities=PRIORITIES)


@tickets_bp.get("/search")
@login_required
def search():
    return index()


@tickets_bp.get("/<int:ticket_id>")
@login_required
def detail(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    areas = Area.query.filter_by(active=True).order_by(Area.name).all()
    return render_template("tickets/detail.html", ticket=ticket, areas=areas, statuses=TICKET_STATUSES)


@tickets_bp.route("/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_ticket")
def edit(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    areas = Area.query.filter_by(active=True).order_by(Area.name).all()
    templates = TicketTemplate.query.filter_by(active=True).order_by(TicketTemplate.name).all()
    if request.method == "POST":
        old_value = f"{ticket.title}|{ticket.status}|{ticket.responsible_area_id}"
        ticket.title = request.form.get("title", "").strip()
        ticket.description = request.form.get("description", "").strip()
        ticket.subtype = request.form.get("subtype")
        ticket.responsible_area_id = int(request.form.get("responsible_area_id"))
        ticket.priority = request.form.get("priority") or None
        ticket.location = request.form.get("location") or None
        ticket.station = request.form.get("station") or None
        ticket.affected_equipment = request.form.get("affected_equipment") or None
        ticket.tags = request.form.get("tags") or None
        ticket.template_id = int(request.form.get("template_id")) if request.form.get("template_id") else None
        log_action("ticket_edited", "Ticket", ticket.id, old_value=old_value, new_value=f"{ticket.title}|{ticket.status}|{ticket.responsible_area_id}")
        db.session.commit()
        flash("Ticket actualizado.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))
    return render_template("tickets/edit.html", ticket=ticket, areas=areas, templates=templates, subtypes=TICKET_SUBTYPES, priorities=PRIORITIES)


@tickets_bp.post("/<int:ticket_id>/comment")
@login_required
def comment(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    if request.form.get("comment", "").strip():
        add_comment(ticket, current_user, request.form["comment"])
        db.session.commit()
        flash("Comentario agregado.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.post("/<int:ticket_id>/status")
@login_required
def status(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    action_map = {
        "Reconocido": "can_acknowledge_ticket",
        "En curso": "can_resolve_ticket",
        "Pendiente de tercero": "can_resolve_ticket",
        "Resuelto": "can_resolve_ticket",
        "Cerrado": "can_resolve_ticket",
        "Reabierto": "can_resolve_ticket",
    }
    new_status = request.form.get("status")
    if new_status not in action_map or not current_user.has_permission(action_map[new_status]):
        abort(403)
    change_status(ticket, new_status, current_user, request.form.get("comment"))
    db.session.commit()
    flash("Estado actualizado.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.post("/<int:ticket_id>/transfer")
@login_required
@require_permission("can_transfer_ticket")
def transfer(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    try:
        transfer_ticket(ticket, request.form.get("to_area_id"), request.form.get("reason"), current_user)
        db.session.commit()
        flash("Ticket derivado.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.post("/<int:ticket_id>/attachments")
@login_required
def attachments(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    save_attachments(ticket, request.files.getlist("attachments"), current_user)
    db.session.commit()
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.get("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    get_visible_ticket(attachment.ticket_id)
    return send_file(attachment.path, as_attachment=True, download_name=attachment.filename_original)
