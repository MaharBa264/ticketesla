import logging

from flask import Flask, g, redirect, request, session, url_for
from flask_login import current_user

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate
from app.models import User
from app.services.auth_service import authenticate_from_persistent_cookie
from app.time_utils import format_datetime_ar


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    logging.basicConfig(level=app.config["LOG_LEVEL"])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Iniciá sesión para continuar."

    from app.blueprints.api.routes import api_bp
    from app.blueprints.audit.routes import audit_bp
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.calendar.routes import calendar_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.templates_admin.routes import templates_bp
    from app.blueprints.tickets.routes import tickets_bp
    from app.blueprints.users.routes import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(audit_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    app.jinja_env.filters["datetime_ar"] = format_datetime_ar

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def load_persistent_login():
        session.permanent = True
        if current_user.is_anonymous:
            authenticate_from_persistent_cookie()
        g.user = current_user

        if current_user.is_authenticated and not current_user.gmail:
            endpoint = request.endpoint or ""
            allowed_endpoints = {
                "auth.complete_profile",
                "auth.logout",
                "static",
                "health",
            }
            if endpoint not in allowed_endpoints and not endpoint.startswith("api."):
                return redirect(url_for("auth.complete_profile", next=request.full_path))

    @app.context_processor
    def inject_helpers():
        return {"has_perm": lambda name: current_user.is_authenticated and current_user.has_permission(name)}

    @app.get("/health")
    def health():
        return {"status": "OK", "version": app.config["RELEASE_VERSION"]}

    @app.get("/login")
    def login_shortcut():
        return redirect(url_for("auth.login"))

    return app
