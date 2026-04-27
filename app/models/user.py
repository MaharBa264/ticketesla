from datetime import timedelta
from hashlib import sha256

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.time_utils import now_utc

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)

user_permissions = db.Table(
    "user_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)

user_visible_areas = db.Table(
    "user_visible_areas",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("area_id", db.Integer, db.ForeignKey("areas.id"), primary_key=True),
)


class Area(db.Model):
    __tablename__ = "areas"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return self.name


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(160))


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(160))
    permissions = db.relationship("Permission", secondary=role_permissions, lazy="selectin")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(160), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    gmail = db.Column(db.String(160), unique=True, nullable=True)
    corporate_email = db.Column(db.String(160))
    phone = db.Column(db.String(50))
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))
    main_area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)
    main_area = db.relationship("Area", foreign_keys=[main_area_id])
    roles = db.relationship("Role", secondary=user_roles, lazy="selectin")
    direct_permissions = db.relationship("Permission", secondary=user_permissions, lazy="selectin")
    visible_areas = db.relationship("Area", secondary=user_visible_areas, lazy="selectin")

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission_name):
        names = {p.name for p in self.direct_permissions}
        for role in self.roles:
            names.update(p.name for p in role.permissions)
        return permission_name in names

    def can_view_area(self, area_id):
        if self.has_permission("can_view_all_tickets") or self.has_permission("can_manage_users"):
            return True
        return self.has_permission("can_view_other_areas") and any(a.id == area_id for a in self.visible_areas)


class PersistentLoginToken(db.Model):
    __tablename__ = "persistent_login_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    selector = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True))
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(80))
    user = db.relationship("User", backref="persistent_tokens")

    @staticmethod
    def hash_token(token):
        return sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def expiry_from_now(cls, days):
        return now_utc() + timedelta(days=days)

    @property
    def active(self):
        return self.revoked_at is None and self.expires_at > now_utc()
