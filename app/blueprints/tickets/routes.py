from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, Ticket, TicketAttachment, TicketTemplate, TICKET_STATUSES, TICKET_SUBTYPES, TICKET_TYPES, PRIORITIES
from app.services.permission_service import (
    can_operate_ticket,
    can_see_expanded_tickets,
    can_transfer_ticket as user_can_transfer_ticket,
    can_view_ticket,
    get_visible_ticket_query,
    require_permission,
)
from app.services.audit_service import log_action
from app.services.ticket_service import add_comment, allowed_status_actions, change_status, create_ticket, is_status_action_allowed, save_attachments, transfer_ticket, validate_ticket_minimum_content

tickets_bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def get_visible_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_view_ticket(ticket, current_user):
        abort(403)
    return ticket


@tickets_bp.get("/")
@login_required
def index():
    requested_scope = request.args.get("scope")
    if request.args.get("mine"):
        requested_scope = "mine"
    default_scope = "visible" if can_see_expanded_tickets(current_user) else "mine"
    scope = requested_scope or default_scope
    if scope not in ("mine", "attend", "visible"):
        scope = default_scope
    query = get_visible_ticket_query(current_user, scope=scope)
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
    return render_template(
        "tickets/index.html",
        tickets=tickets,
        statuses=TICKET_STATUSES,
        types=TICKET_TYPES,
        areas=Area.query.order_by(Area.name).all(),
        scope=scope,
        can_see_expanded=can_see_expanded_tickets(current_user),
    )


@tickets_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("can_create_ticket")
def create():
    areas = Area.query.filter_by(active=True).order_by(Area.name).all()
    templates = TicketTemplate.query.filter_by(active=True).order_by(TicketTemplate.name).all()
    if request.method == "POST":
        try:
            uploaded_files = request.files.getlist("attachments")
            validate_ticket_minimum_content(request.form, uploaded_files)
            ticket = create_ticket(request.form, current_user)
            attachment_result = save_attachments(ticket, uploaded_files, current_user)
            db.session.commit()
            flash(f"Ticket {ticket.number} creado.", "success")
            if attachment_result["errors"]:
                flash("El ticket fue guardado, pero no se pudo cargar uno o más adjuntos.", "warning")
            return redirect(url_for("tickets.detail", ticket_id=ticket.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")
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
    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        areas=areas,
        statuses=TICKET_STATUSES,
        status_actions=allowed_status_actions(ticket, current_user),
        can_operate=can_operate_ticket(ticket, current_user),
        can_edit_ticket=can_operate_ticket(ticket, current_user, "can_edit_ticket"),
        can_transfer_ticket=user_can_transfer_ticket(ticket, current_user),
    )


@tickets_bp.route("/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("can_edit_ticket")
def edit(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    if not can_operate_ticket(ticket, current_user, "can_edit_ticket"):
        abort(403)
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
    new_status = request.form.get("status")
    if not is_status_action_allowed(ticket, new_status, current_user):
        abort(403)
    extra_hand_granted = change_status(ticket, new_status, current_user, request.form.get("comment"))
    db.session.commit()
    flash("Estado actualizado.", "success")
    if extra_hand_granted:
        flash("Ganaste +1 mano extra en Poker de los Izquierdos.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.post("/<int:ticket_id>/transfer")
@login_required
@require_permission("can_transfer_ticket")
def transfer(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    if not user_can_transfer_ticket(ticket, current_user):
        abort(403)
    try:
        transfer = transfer_ticket(ticket, request.form.get("to_area_id"), request.form.get("reason"), current_user)
        db.session.commit()
        flash(f"Ticket derivado correctamente a {transfer.to_area.name}.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.post("/<int:ticket_id>/attachments")
@login_required
def attachments(ticket_id):
    ticket = get_visible_ticket(ticket_id)
    result = save_attachments(ticket, request.files.getlist("attachments"), current_user)
    db.session.commit()
    if result["saved"]:
        flash("Adjunto cargado correctamente.", "success")
    if result["errors"]:
        flash("No se pudo cargar el adjunto. Verificá el tamaño o formato.", "warning")
    return redirect(url_for("tickets.detail", ticket_id=ticket.id))


@tickets_bp.get("/<int:ticket_id>/attachments/<int:attachment_id>/download")
@login_required
def download_ticket_attachment(ticket_id, attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    if attachment.ticket_id != ticket_id:
        abort(404)
    get_visible_ticket(attachment.ticket_id)
    return send_file(attachment.path, as_attachment=True, download_name=attachment.filename_original)


@tickets_bp.get("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    get_visible_ticket(attachment.ticket_id)
    return send_file(attachment.path, as_attachment=True, download_name=attachment.filename_original)
