import secrets

from flask import current_app, request
from flask_login import login_user, logout_user

from app.extensions import db
from app.models import PersistentLoginToken, User
from app.time_utils import now_utc


def create_persistent_login(user):
    selector = secrets.token_urlsafe(24)
    validator = secrets.token_urlsafe(48)
    token = PersistentLoginToken(
        user=user,
        selector=selector,
        token_hash=PersistentLoginToken.hash_token(validator),
        expires_at=PersistentLoginToken.expiry_from_now(current_app.config["REMEMBER_COOKIE_DAYS"]),
        user_agent=request.user_agent.string[:255] if request.user_agent else None,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    db.session.add(token)
    db.session.commit()
    return f"{selector}:{validator}", token.expires_at


def set_remember_cookie(response, cookie_value, expires):
    response.set_cookie(
        current_app.config["REMEMBER_COOKIE_NAME"],
        cookie_value,
        expires=expires,
        httponly=True,
        secure=current_app.config["REMEMBER_COOKIE_SECURE"],
        samesite=current_app.config["REMEMBER_COOKIE_SAMESITE"],
    )


def clear_remember_cookie(response):
    response.delete_cookie(current_app.config["REMEMBER_COOKIE_NAME"])


def authenticate_from_persistent_cookie():
    raw = request.cookies.get(current_app.config["REMEMBER_COOKIE_NAME"])
    if not raw or ":" not in raw:
        return
    selector, validator = raw.split(":", 1)
    token = PersistentLoginToken.query.filter_by(selector=selector).first()
    if not token or not token.active:
        return
    if token.token_hash != PersistentLoginToken.hash_token(validator):
        token.revoked_at = now_utc()
        db.session.commit()
        return
    user = User.query.get(token.user_id)
    if user and user.active:
        login_user(user)


def revoke_current_cookie_token():
    raw = request.cookies.get(current_app.config["REMEMBER_COOKIE_NAME"])
    if raw and ":" in raw:
        selector = raw.split(":", 1)[0]
        token = PersistentLoginToken.query.filter_by(selector=selector, revoked_at=None).first()
        if token:
            token.revoked_at = now_utc()
            db.session.commit()
    logout_user()
