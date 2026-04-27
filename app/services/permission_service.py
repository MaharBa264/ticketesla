from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user


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


def visible_area_ids(user):
    ids = {user.main_area_id}
    if user.has_permission("can_view_other_areas"):
        ids.update(area.id for area in user.visible_areas)
    return ids
