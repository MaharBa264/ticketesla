from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user

from app.extensions import db
from app.models import Area, Role, User
from app.services.auth_service import clear_remember_cookie, create_persistent_login, revoke_current_cookie_token, set_remember_cookie
from app.services.audit_service import log_action
from app.time_utils import now_utc

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.active and user.check_password(request.form.get("password", "")):
            user.last_login_at = now_utc()
            login_user(user)
            log_action("login", "User", user.id, user=user)
            db.session.commit()
            response = make_response(redirect(url_for("dashboard.index")))
            if request.form.get("remember"):
                cookie, expires = create_persistent_login(user)
                set_remember_cookie(response, cookie, expires)
            return response
        flash("Usuario o contraseña inválidos.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    areas = Area.query.filter_by(active=True).order_by(Area.name).all()
    if request.method == "POST":
        gmail = request.form.get("gmail", "").strip().lower()
        if not gmail.endswith("@gmail.com"):
            flash("El correo Gmail debe terminar en @gmail.com.", "warning")
            return render_template("auth/register.html", areas=areas)
        if User.query.filter((User.username == request.form.get("username")) | (User.gmail == gmail)).first():
            flash("Ya existe un usuario con ese username o Gmail.", "warning")
            return render_template("auth/register.html", areas=areas)
        role = Role.query.filter_by(name="Solicitante").first()
        user = User(
            full_name=request.form.get("full_name", "").strip(),
            username=request.form.get("username", "").strip(),
            gmail=gmail,
            corporate_email=request.form.get("corporate_email") or None,
            phone=request.form.get("phone") or None,
            main_area_id=int(request.form.get("main_area_id")),
            active=True,
        )
        user.set_password(request.form.get("password", ""))
        if role:
            user.roles.append(role)
        db.session.add(user)
        db.session.flush()
        log_action("user_registered", "User", user.id, user=user)
        db.session.commit()
        flash("Usuario creado. Ya podés iniciar sesión.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", areas=areas)


@auth_bp.post("/logout")
@login_required
def logout():
    revoke_current_cookie_token()
    response = make_response(redirect(url_for("auth.login")))
    clear_remember_cookie(response)
    return response
