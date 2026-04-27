from flask import request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def log_action(action, entity_type, entity_id=None, old_value=None, new_value=None, user=None):
    actor = user
    if actor is None and current_user and not current_user.is_anonymous:
        actor = current_user
    entry = AuditLog(
        user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
        user_agent=(request.user_agent.string[:255] if request and request.user_agent else None),
    )
    db.session.add(entry)
    return entry
