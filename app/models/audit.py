from app.extensions import db
from app.time_utils import now_utc


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(80))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False, index=True)
    ip_address = db.Column(db.String(80))
    user_agent = db.Column(db.String(255))
    user = db.relationship("User")
