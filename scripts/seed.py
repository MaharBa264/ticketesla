import os

from app.models import Area, Permission, Role, TicketTemplate, User

AREAS = ["Comunicaciones", "Protecciones", "Telecontrol", "SCADA"]

PERMISSIONS = [
    "can_create_ticket",
    "can_acknowledge_ticket",
    "can_resolve_ticket",
    "can_transfer_ticket",
    "can_view_other_areas",
    "can_edit_templates",
    "can_manage_users",
    "can_manage_catalogs",
    "can_view_audit_log",
    "can_edit_ticket",
]

ROLE_PERMISSIONS = {
    "Solicitante": ["can_create_ticket"],
    "Operador de área": ["can_create_ticket", "can_acknowledge_ticket", "can_resolve_ticket", "can_edit_ticket"],
    "Coordinador / Derivador": ["can_create_ticket", "can_acknowledge_ticket", "can_resolve_ticket", "can_transfer_ticket", "can_view_other_areas", "can_edit_ticket"],
    "Editor de plantillas": ["can_create_ticket", "can_edit_templates"],
    "Administrador": PERMISSIONS,
}

TEMPLATES = [
    ("Registro de cambio de IP", "Comunicaciones", "Registro de cambio", "Corrección", "Equipo:\nIP anterior:\nIP nueva:\nMotivo del cambio:\nValidación realizada:"),
    ("Registro de cambio de ajuste de protección", "Protecciones", "Registro de cambio", "Revisión", "Protección:\nAjuste anterior:\nAjuste nuevo:\nMotivo:\nEvidencia:"),
    ("Registro de cambio en base SCADA", "SCADA", "Registro de cambio", "Corrección", "Base/servidor:\nObjeto modificado:\nCambio realizado:\nPrueba posterior:"),
    ("Solicitud de corrección de señal", "SCADA", "Solicitud de intervención", "Corrección", "Señal afectada:\nComportamiento observado:\nComportamiento esperado:\nPrioridad operativa:"),
    ("Solicitud de revisión de comunicación", "Comunicaciones", "Solicitud de intervención", "Revisión", "Equipo/RTU:\nSíntoma:\nDesde cuándo ocurre:\nPruebas ya realizadas:"),
    ("Solicitud de asistencia técnica", "Telecontrol", "Solicitud de intervención", "Asistencia", "Necesidad:\nSistema/equipo:\nFecha requerida:\nContacto operativo:"),
    ("Plantilla base genérica", "Telecontrol", "Solicitud de intervención", "Otro", "Detalle:\nImpacto:\nAcción solicitada:"),
]


def get_or_create(session, model, defaults=None, **kwargs):
    obj = session.query(model).filter_by(**kwargs).first()
    if obj:
        return obj
    obj = model(**kwargs)
    for key, value in (defaults or {}).items():
        setattr(obj, key, value)
    session.add(obj)
    session.flush()
    return obj


def seed_data(session):
    areas = {name: get_or_create(session, Area, name=name) for name in AREAS}
    permissions = {name: get_or_create(session, Permission, name=name) for name in PERMISSIONS}
    for role_name, permission_names in ROLE_PERMISSIONS.items():
        role = get_or_create(session, Role, name=role_name)
        role.permissions = [permissions[name] for name in permission_names]

    admin_username = os.getenv("TICKETESLA_ADMIN_USERNAME")
    admin_password = os.getenv("TICKETESLA_ADMIN_PASSWORD")
    admin_email = os.getenv("TICKETESLA_ADMIN_EMAIL")
    admin_name = os.getenv("TICKETESLA_ADMIN_NAME", "Administrador Ticketesla")
    if admin_username and admin_password and admin_email:
        admin = session.query(User).filter_by(username=admin_username).first()
        if not admin:
            admin = User(
                username=admin_username,
                full_name=admin_name,
                gmail=admin_email,
                main_area=areas["Telecontrol"],
                active=True,
            )
            admin.set_password(admin_password)
            session.add(admin)
        admin.roles = [session.query(Role).filter_by(name="Administrador").one()]
        admin.visible_areas = list(areas.values())

    for name, area_name, ticket_type, subtype, body in TEMPLATES:
        if not session.query(TicketTemplate).filter_by(name=name).first():
            session.add(TicketTemplate(name=name, area=areas[area_name], suggested_type=ticket_type, suggested_subtype=subtype, body=body, active=True))
