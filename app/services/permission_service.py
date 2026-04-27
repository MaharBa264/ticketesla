from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.models import Ticket

GLOBAL_TICKET_PERMISSIONS = ("can_view_all_tickets", "can_manage_users")
AREA_VIEW_PERMISSIONS = ("can_view_other_areas",)
AREA_OPERATION_PERMISSIONS = (
    "can_acknowledge_ticket",
    "can_resolve_ticket",
    "can_transfer_ticket",
    "can_reopen_ticket",
    "can_edit_ticket",
)


def has_permission(user, permission_name):
    return bool(user and user.is_authenticated and user.has_permission(permission_name))


def require_permission(permission_name):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not has_permission(current_user, permission_name):
                if request.accept_mimetypes.best == "application/json" or request.path.startswith("/api/"):
                    abort(403)
                flash("No tenés permisos para realizar esa acción.", "warning")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def has_global_ticket_access(user):
    return bool(user and user.is_authenticated and any(user.has_permission(name) for name in GLOBAL_TICKET_PERMISSIONS))


def has_any_area_operation_permission(user):
    return bool(user and user.is_authenticated and any(user.has_permission(name) for name in AREA_OPERATION_PERMISSIONS))


def explicit_visible_area_ids(user):
    if not user or not user.is_authenticated:
        return set()
    return {area.id for area in user.visible_areas}


def visible_area_ids(user):
    """Areas explicitly granted to the user. The main area is not implicit visibility."""
    if has_global_ticket_access(user):
        return {area.id for area in getattr(user, "visible_areas", [])}
    if user and user.is_authenticated and (user.has_permission("can_view_other_areas") or has_any_area_operation_permission(user)):
        return explicit_visible_area_ids(user)
    return set()


def can_see_expanded_tickets(user):
    return has_global_ticket_access(user) or bool(visible_area_ids(user))


def can_view_ticket(ticket, user):
    if not user or not user.is_authenticated or ticket is None:
        return False
    if ticket.creator_user_id == user.id:
        return True
    if has_global_ticket_access(user):
        return True
    area_ids = visible_area_ids(user)
    return ticket.responsible_area_id in area_ids or ticket.creator_area_id in area_ids


def can_operate_ticket(ticket, user, permission_name=None):
    if not user or not user.is_authenticated or ticket is None:
        return False
    if permission_name and not user.has_permission(permission_name):
        return False
    if permission_name is None and not has_any_area_operation_permission(user):
        return False
    if has_global_ticket_access(user):
        return True
    return ticket.responsible_area_id in visible_area_ids(user)


def get_visible_ticket_query(user, scope="visible"):
    query = Ticket.query
    if not user or not user.is_authenticated:
        return query.filter(Ticket.id == None)
    if scope == "mine":
        return query.filter(Ticket.creator_user_id == user.id)
    if scope == "attend":
        if has_global_ticket_access(user) and has_any_area_operation_permission(user):
            return query
        area_ids = visible_area_ids(user)
        if not area_ids or not has_any_area_operation_permission(user):
            return query.filter(Ticket.id == None)
        return query.filter(Ticket.responsible_area_id.in_(area_ids))
    if has_global_ticket_access(user):
        return query
    area_ids = visible_area_ids(user)
    if not area_ids:
        return query.filter(Ticket.creator_user_id == user.id)
    return query.filter(
        or_(
            Ticket.creator_user_id == user.id,
            Ticket.responsible_area_id.in_(area_ids),
            Ticket.creator_area_id.in_(area_ids),
        )
    )
