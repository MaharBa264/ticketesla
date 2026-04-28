from app.extensions import db
from app.time_utils import now_utc

TICKET_TYPES = ("Registro de cambio", "Solicitud de intervención")
TICKET_SUBTYPES = ("Corrección", "Nuevo requerimiento", "Revisión", "Asistencia", "Otro")
TICKET_STATUSES = (
    "Nuevo",
    "Reconocido",
    "En curso",
    "Derivado",
    "Pendiente de tercero",
    "Resuelto",
    "Cerrado",
    "Reabierto",
)
ACTIVE_TICKET_STATUSES = (
    "Nuevo",
    "Reconocido",
    "En curso",
    "Derivado",
    "Pendiente de tercero",
)
FINAL_TICKET_STATUSES = ("Resuelto", "Cerrado")
PRIORITIES = ("Baja", "Normal", "Alta", "Urgente")


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ticket_type = db.Column(db.String(60), nullable=False)
    subtype = db.Column(db.String(60), nullable=False)
    creator_area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    responsible_area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    creator_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(60), default="Nuevo", nullable=False, index=True)
    priority = db.Column(db.String(30))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    due_at = db.Column(db.DateTime(timezone=True))
    closed_at = db.Column(db.DateTime(timezone=True))
    tags = db.Column(db.String(255))
    location = db.Column(db.String(160))
    station = db.Column(db.String(160))
    affected_equipment = db.Column(db.String(160))
    template_id = db.Column(db.Integer, db.ForeignKey("ticket_templates.id"))
    structured_data = db.Column(db.JSON)

    creator_area = db.relationship("Area", foreign_keys=[creator_area_id])
    responsible_area = db.relationship("Area", foreign_keys=[responsible_area_id])
    creator = db.relationship("User", foreign_keys=[creator_user_id])
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id])
    template = db.relationship("TicketTemplate")
    comments = db.relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    status_history = db.relationship("TicketStatusHistory", back_populates="ticket", cascade="all, delete-orphan")
    transfers = db.relationship("TicketTransfer", back_populates="ticket", cascade="all, delete-orphan")
    attachments = db.relationship("TicketAttachment", back_populates="ticket", cascade="all, delete-orphan")


class TicketComment(db.Model):
    __tablename__ = "ticket_comments"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    comment_type = db.Column(db.String(40))
    ticket = db.relationship("Ticket", back_populates="comments")
    user = db.relationship("User")


class TicketStatusHistory(db.Model):
    __tablename__ = "ticket_status_history"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    old_status = db.Column(db.String(60))
    new_status = db.Column(db.String(60), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    comment = db.Column(db.Text)
    ticket = db.relationship("Ticket", back_populates="status_history")
    user = db.relationship("User")


class TicketTransfer(db.Model):
    __tablename__ = "ticket_transfers"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    from_area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    to_area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    ticket = db.relationship("Ticket", back_populates="transfers")
    from_area = db.relationship("Area", foreign_keys=[from_area_id])
    to_area = db.relationship("Area", foreign_keys=[to_area_id])
    user = db.relationship("User")


class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    filename_original = db.Column(db.String(255), nullable=False)
    filename_storage = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(120))
    size = db.Column(db.Integer, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    ticket = db.relationship("Ticket", back_populates="attachments")
    user = db.relationship("User")
