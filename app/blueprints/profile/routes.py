from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import User
from app.services.audit_service import log_action

profile_bp = Blueprint("profile", __name__)


def _safe_next():
    value = request.form.get("next") or request.args.get("next") or ""
    if value.startswith("/") and not value.startswith("//") and not value.startswith("/profile"):
        return value
    return url_for("dashboard.index")


def _validate_gmail(gmail):
    gmail = (gmail or "").strip().lower()
    if not gmail:
        return None, "El correo Gmail es obligatorio."
    if not gmail.endswith("@gmail.com"):
        return None, "El correo Gmail debe terminar en @gmail.com."
    existing = User.query.filter(User.gmail == gmail, User.id != current_user.id).first()
    if existing:
        return None, "Ese correo Gmail ya está asociado a otro usuario."
    return gmail, None


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def index():
    must_complete_gmail = not current_user.gmail
    next_url = _safe_next()
    if request.method == "POST":
        gmail, error = _validate_gmail(request.form.get("gmail"))
        if error:
            flash(error, "warning")
            return render_template("profile/index.html", must_complete_gmail=must_complete_gmail, next_url=next_url)

        old_value = f"{current_user.full_name}|{current_user.gmail}|{current_user.corporate_email}|{current_user.phone}"
        current_user.full_name = request.form.get("full_name", "").strip() or current_user.full_name
        current_user.gmail = gmail
        current_user.corporate_email = request.form.get("corporate_email", "").strip() or None
        current_user.phone = request.form.get("phone", "").strip() or None
        new_value = f"{current_user.full_name}|{current_user.gmail}|{current_user.corporate_email}|{current_user.phone}"
        log_action("profile_updated", "User", current_user.id, old_value=old_value, new_value=new_value, user=current_user)
        db.session.commit()
        flash("Perfil actualizado correctamente.", "success")
        return redirect(next_url)

    if must_complete_gmail:
        flash("Antes de continuar, completá tu correo Gmail.", "warning")
    return render_template("profile/index.html", must_complete_gmail=must_complete_gmail, next_url=next_url)


@profile_bp.post("/profile/password")
@login_required
def password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_user.check_password(current_password):
        flash("La contraseña actual no es correcta.", "warning")
        return redirect(url_for("profile.index"))
    if len(new_password) < 8:
        flash("La nueva contraseña debe tener al menos 8 caracteres.", "warning")
        return redirect(url_for("profile.index"))
    if new_password != confirm_password:
        flash("La nueva contraseña y su repetición no coinciden.", "warning")
        return redirect(url_for("profile.index"))

    current_user.set_password(new_password)
    log_action("password_changed", "User", current_user.id, user=current_user)
    db.session.commit()
    flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("profile.index"))
