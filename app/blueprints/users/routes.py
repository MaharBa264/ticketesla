from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Area, Permission, PersistentLoginToken, Role, User
from app.services.audit_service import log_action
from app.services.permission_service import require_permission
from app.time_utils import now_utc

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.get("/")
@login_required
@require_permission("can_manage_users")
def index():
    return render_template("users/index.html", users=User.query.order_by(User.full_name).all())


@users_bp.route("/new", methods=["GET", "POST"])
@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("can_manage_users")
def edit(user_id=None):
    user = User.query.get(user_id) if user_id else None
    areas = Area.query.order_by(Area.name).all()
    roles = Role.query.order_by(Role.name).all()
    permissions = Permission.query.order_by(Permission.name).all()
    if request.method == "POST":
        gmail = request.form.get("gmail", "").strip().lower()
        if not gmail.endswith("@gmail.com"):
            flash("El correo Gmail debe terminar en @gmail.com.", "warning")
            return render_template("users/edit.html", user=user, areas=areas, roles=roles, permissions=permissions)
        if user is None:
            user = User()
            db.session.add(user)
        user.full_name = request.form.get("full_name", "").strip()
        user.username = request.form.get("username", "").strip()
        user.gmail = gmail
        user.corporate_email = request.form.get("corporate_email") or None
        user.phone = request.form.get("phone") or None
        user.main_area_id = int(request.form.get("main_area_id"))
        user.active = bool(request.form.get("active"))
        if request.form.get("password"):
            user.set_password(request.form["password"])
        user.roles = Role.query.filter(Role.id.in_([int(x) for x in request.form.getlist("roles")])).all()
        user.direct_permissions = Permission.query.filter(Permission.id.in_([int(x) for x in request.form.getlist("permissions")])).all()
        user.visible_areas = Area.query.filter(Area.id.in_([int(x) for x in request.form.getlist("visible_areas")])).all()
        db.session.flush()
        log_action("user_saved", "User", user.id)
        db.session.commit()
        flash("Usuario guardado.", "success")
        return redirect(url_for("users.index"))
    return render_template("users/edit.html", user=user, areas=areas, roles=roles, permissions=permissions)


@users_bp.post("/<int:user_id>/revoke-tokens")
@login_required
@require_permission("can_manage_users")
def revoke_tokens(user_id):
    tokens = PersistentLoginToken.query.filter_by(user_id=user_id, revoked_at=None).all()
    for token in tokens:
        token.revoked_at = now_utc()
    log_action("user_tokens_revoked", "User", user_id, new_value=str(len(tokens)))
    db.session.commit()
    flash("Sesiones persistentes revocadas.", "success")
    return redirect(url_for("users.edit", user_id=user_id))
