import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


def _split_recipients(recipients):
    if not recipients:
        return []
    if isinstance(recipients, str):
        recipients = [recipients]
    seen = set()
    clean = []
    for recipient in recipients:
        email = (recipient or "").strip()
        key = email.lower()
        if email and key not in seen:
            seen.add(key)
            clean.append(email)
    debug_to = current_app.config.get("EMAIL_DEBUG_TO")
    return [debug_to] if debug_to else clean


def send_email(recipients, subject, body):
    to = _split_recipients(recipients)
    if not to:
        logger.info("Email omitido por falta de destinatarios: %s", subject)
        return False
    if not current_app.config.get("EMAIL_ENABLED"):
        logger.info("Email omitido porque EMAIL_ENABLED=false: %s -> %s", subject, ", ".join(to))
        return False
    if current_app.config.get("EMAIL_DRY_RUN"):
        logger.info("EMAIL_DRY_RUN: se enviaría '%s' a %s\n%s", subject, ", ".join(to), body)
        return True

    host = current_app.config.get("SMTP_HOST")
    sender = current_app.config.get("SMTP_FROM")
    if not host or not sender:
        logger.warning("Email omitido por configuración SMTP incompleta: SMTP_HOST/SMTP_FROM")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(to)
    message.set_content(body)

    try:
        smtp_class = smtplib.SMTP_SSL if current_app.config.get("SMTP_USE_SSL") else smtplib.SMTP
        with smtp_class(host, current_app.config.get("SMTP_PORT"), timeout=current_app.config.get("SMTP_TIMEOUT")) as smtp:
            if current_app.config.get("SMTP_USE_TLS") and not current_app.config.get("SMTP_USE_SSL"):
                smtp.starttls()
            username = current_app.config.get("SMTP_USERNAME")
            password = current_app.config.get("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        logger.info("Email enviado: %s -> %s", subject, ", ".join(to))
        return True
    except Exception:
        logger.exception("Error enviando email: %s", subject)
        return False
