import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import parseaddr

from flask import current_app

logger = logging.getLogger(__name__)


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "si", "sí"}


def _split_emails(value):
    if not value:
        return []
    raw = str(value).replace(";", ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _unique_recipients(recipients):
    seen = set()
    result = []
    for email in recipients or []:
        email = (email or "").strip()
        if not email:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(email)
    return result


def _required_smtp_config():
    return {
        "host": current_app.config.get("SMTP_HOST"),
        "port": int(current_app.config.get("SMTP_PORT") or 587),
        "use_tls": _as_bool(current_app.config.get("SMTP_USE_TLS"), True),
        "use_ssl": _as_bool(current_app.config.get("SMTP_USE_SSL"), False),
        "username": current_app.config.get("SMTP_USERNAME"),
        "password": current_app.config.get("SMTP_PASSWORD"),
        "sender": current_app.config.get("SMTP_FROM"),
        "timeout": int(current_app.config.get("SMTP_TIMEOUT") or 10),
    }


def send_email(subject, body, recipients):
    """Envía un email de texto plano o lo registra en logs según configuración.

    Nunca debe romper el flujo principal de tickets: ante error, registra y devuelve False.
    """
    recipients = _unique_recipients(recipients)
    debug_to = _split_emails(current_app.config.get("EMAIL_DEBUG_TO"))
    if debug_to:
        logger.info("EMAIL_DEBUG_TO activo: reemplazando destinatarios reales %s por %s", recipients, debug_to)
        recipients = debug_to

    if not recipients:
        logger.info("Email omitido por falta de destinatarios: %s", subject)
        return False

    enabled = _as_bool(current_app.config.get("EMAIL_ENABLED"), False)
    dry_run = _as_bool(current_app.config.get("EMAIL_DRY_RUN"), True)

    if not enabled:
        logger.info("Email omitido porque EMAIL_ENABLED=false: %s -> %s", subject, ", ".join(recipients))
        return False

    if dry_run:
        logger.info("Email dry-run: %s -> %s\n%s", subject, ", ".join(recipients), body)
        return True

    cfg = _required_smtp_config()
    missing = [name for name in ("host", "sender") if not cfg.get(name)]
    if missing:
        logger.warning("Email omitido por configuración SMTP incompleta (%s): %s", ", ".join(missing), subject)
        return False

    message = MIMEText(body or "", "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = cfg["sender"]
    message["To"] = ", ".join(recipients)

    try:
        if cfg["use_ssl"]:
            smtp = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=cfg["timeout"])
        else:
            smtp = smtplib.SMTP(cfg["host"], cfg["port"], timeout=cfg["timeout"])
        with smtp:
            smtp.ehlo()
            if cfg["use_tls"] and not cfg["use_ssl"]:
                smtp.starttls()
                smtp.ehlo()
            if cfg["username"] or cfg["password"]:
                if not (cfg["username"] and cfg["password"]):
                    logger.warning("Email omitido por configuración SMTP incompleta (username/password parcial): %s", subject)
                    return False
                smtp.login(cfg["username"], cfg["password"])
            else:
                logger.info("SMTP sin autenticación: usando relay interno sin login")
            envelope_sender = parseaddr(cfg["sender"])[1] or cfg["sender"]
            smtp.sendmail(envelope_sender, recipients, message.as_string())
        logger.info("Email enviado: %s -> %s", subject, ", ".join(recipients))
        return True
    except Exception:
        logger.exception("Error enviando email: %s -> %s", subject, ", ".join(recipients))
        return False
