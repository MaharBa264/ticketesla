from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Area, GameUserSettings, Permission, PersistentLoginToken, Role, User
from app.services.audit_service import log_action
from app.services.game_service import reset_current_window, status_for
from app.services.permission_service import require_permission
from app.time_utils import now_utc

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _ids_from_form(field_name):
    ids = []
    for raw in request.form.getlist(field_name):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def _render_form(user, areas, roles, permissions):
    game_settings = GameUserSettings.query.get(user.id) if user else None
    game_status = status_for(user) if user else None
    return render_template("users/edit.html", user=user, areas=areas, roles=roles, permissions=permissions, game_settings=game_settings, game_status=game_status)


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
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        gmail_raw = request.form.get("gmail", "").strip().lower()
        gmail = gmail_raw or None
        password = request.form.get("password", "")

        if not full_name or not username:
            flash("Nombre completo y usuario son obligatorios.", "warning")
            return _render_form(user, areas, roles, permissions)

        if user is None and not password:
            flash("La contraseña es obligatoria para crear un usuario nuevo.", "warning")
            return _render_form(user, areas, roles, permissions)

        if gmail and not gmail.endswith("@gmail.com"):
            flash("Si cargás un Gmail, debe terminar en @gmail.com. También podés dejarlo vacío y el usuario lo completará en su primer ingreso.", "warning")
            return _render_form(user, areas, roles, permissions)

        username_query = User.query.filter(User.username == username)
        if user is not None:
            username_query = username_query.filter(User.id != user.id)
        if username_query.first():
            flash("Ya existe otro usuario con ese nombre de usuario.", "warning")
            return _render_form(user, areas, roles, permissions)

        if gmail:
            gmail_query = User.query.filter(User.gmail == gmail)
            if user is not None:
                gmail_query = gmail_query.filter(User.id != user.id)
            if gmail_query.first():
                flash("Ese Gmail ya está asociado a otro usuario. Dejalo vacío o cargá uno diferente.", "warning")
                return _render_form(user, areas, roles, permissions)

        if user is None:
            user = User()
            db.session.add(user)

        user.full_name = full_name
        user.username = username
        user.gmail = gmail
        user.corporate_email = request.form.get("corporate_email") or None
        user.phone = request.form.get("phone") or None
        user.main_area_id = int(request.form.get("main_area_id"))
        user.active = bool(request.form.get("active"))
        if password:
            user.set_password(password)

        role_ids = _ids_from_form("roles")
        permission_ids = _ids_from_form("permissions")
        visible_area_ids = _ids_from_form("visible_areas")

        user.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
        user.direct_permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all() if permission_ids else []
        user.visible_areas = Area.query.filter(Area.id.in_(visible_area_ids)).all() if visible_area_ids else []

        db.session.flush()
        settings = GameUserSettings.query.get(user.id)
        if settings is None:
            settings = GameUserSettings(user_id=user.id)
            db.session.add(settings)
        settings.enabled = bool(request.form.get("game_enabled"))
        settings.ranking_enabled = bool(request.form.get("game_ranking_enabled"))
        try:
            settings.hands_limit = max(1, min(int(request.form.get("game_hands_limit", 3)), 50))
            settings.window_minutes = max(1, min(int(request.form.get("game_window_minutes", 120)), 10080))
        except ValueError:
            settings.hands_limit = 3
            settings.window_minutes = 120
        settings.updated_by = current_user.id
        log_action("user_saved", "User", user.id)
        db.session.commit()
        flash("Usuario guardado.", "success")
        return redirect(url_for("users.index"))

    return _render_form(user, areas, roles, permissions)


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


@users_bp.post("/<int:user_id>/reset-game-window")
@login_required
@require_permission("can_manage_users")
def reset_game_window(user_id):
    user = User.query.get_or_404(user_id)
    reset_current_window(user)
    log_action("game_window_reset", "User", user_id)
    db.session.commit()
    flash("Contador actual del juego reiniciado.", "success")
    return redirect(url_for("users.edit", user_id=user_id))
