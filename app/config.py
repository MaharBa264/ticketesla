import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://ticketesla:ticketesla@localhost:5432/ticketesla"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    REMEMBER_COOKIE_NAME = "ticketesla_remember"
    REMEMBER_COOKIE_DAYS = int(os.getenv("REMEMBER_COOKIE_DAYS", "60"))
    REMEMBER_COOKIE_SECURE = os.getenv("REMEMBER_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.getenv("REMEMBER_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
    STORAGE_PATH = os.getenv("STORAGE_PATH", str(BASE_DIR / "storage"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    RELEASE_VERSION = os.getenv("RELEASE_VERSION", "dev")
    TIMEZONE = "America/Argentina/San_Luis"

    # Email / Office 365 SMTP. Por defecto no envía nada real.
    EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    EMAIL_DRY_RUN = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "smtp")
    BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "10"))
    EMAIL_DEBUG_TO = os.getenv("EMAIL_DEBUG_TO", "")

    ALLOWED_UPLOAD_EXTENSIONS = os.getenv(
        "ALLOWED_UPLOAD_EXTENSIONS",
        "pdf,png,jpg,jpeg,txt,csv,xlsx,docx,zip",
    )
