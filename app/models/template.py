from app.extensions import db
from app.time_utils import now_utc


class TicketTemplate(db.Model):
    __tablename__ = "ticket_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    suggested_type = db.Column(db.String(60), nullable=False)
    suggested_subtype = db.Column(db.String(60), nullable=False)
    body = db.Column(db.Text, nullable=False)
    schema_json = db.Column(db.JSON)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    area = db.relationship("Area")
    creator = db.relationship("User", foreign_keys=[created_by])
    updater = db.relationship("User", foreign_keys=[updated_by])
