import os

from app.models import Area, Permission, Role, TicketTemplate, User

AREAS = ["Comunicaciones", "Protecciones", "Telecontrol", "CMD"]

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
    "can_reopen_ticket",
]

ROLE_PERMISSIONS = {
    "Solicitante": ["can_create_ticket"],
    "Operador de área": ["can_create_ticket", "can_acknowledge_ticket", "can_resolve_ticket", "can_edit_ticket"],
    "Coordinador / Derivador": ["can_create_ticket", "can_acknowledge_ticket", "can_resolve_ticket", "can_transfer_ticket", "can_view_other_areas", "can_edit_ticket"],
    "Editor de plantillas": ["can_create_ticket", "can_edit_templates"],
    "Administrador": PERMISSIONS,
}


def field(label, field_type="text", required=True, placeholder="", help_text="", options=None):
    key = label.lower()
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
        "/": " ", "-": " ", ".": " ", ":": " ", "(": " ", ")": " ",
    }
    for old, new in replacements.items():
        key = key.replace(old, new)
    key = "_".join(part for part in key.split() if part)
    return {
        "key": key,
        "label": label,
        "type": field_type,
        "required": required,
        "placeholder": placeholder,
        "help": help_text,
        "options": options or [],
    }


def schema(*fields):
    return {"version": 1, "fields": list(fields)}


TEMPLATES = [
    {
        "name": "Registro de cambio de IP",
        "area": "Comunicaciones",
        "type": "Registro de cambio",
        "subtype": "Corrección",
        "body": "Registrar el cambio realizado y la validación posterior.",
        "schema": schema(
            field("Equipo", placeholder="RTU / switch / router / IED"),
            field("IP anterior", placeholder="192.168.1.10"),
            field("IP nueva", placeholder="192.168.1.20"),
            field("Motivo del cambio", "textarea"),
            field("Validación realizada", "textarea", help_text="Ping, acceso web, CMD, prueba de comunicación, etc."),
        ),
    },
    {
        "name": "Registro de cambio de ajuste de protección",
        "area": "Protecciones",
        "type": "Registro de cambio",
        "subtype": "Revisión",
        "body": "Registrar un cambio ya ejecutado sobre un ajuste de protección.",
        "schema": schema(
            field("Estación"),
            field("Protección / IED", placeholder="Ej.: REF615, RET650, 7SJ"),
            field("Función modificada", placeholder="Ej.: 50/51, 50N/51N, 67N"),
            field("Ajuste anterior", "textarea"),
            field("Ajuste nuevo", "textarea"),
            field("Motivo" , "textarea"),
            field("Evidencia / archivo adjunto", "checkbox", required=False, help_text="Marcar si se adjunta respaldo o captura."),
        ),
    },
    {
        "name": "Registro de cambio en base CMD",
        "area": "CMD",
        "type": "Registro de cambio",
        "subtype": "Corrección",
        "body": "Registrar cambios realizados sobre base, objeto, señal o despliegue CMD.",
        "schema": schema(
            field("Sistema / servidor", placeholder="eTerra, Archive, HMI, servidor, etc."),
            field("Objeto modificado", placeholder="Señal, display, punto, equipo, dataset"),
            field("Cambio realizado", "textarea"),
            field("Prueba posterior", "textarea"),
        ),
    },
    {
        "name": "Solicitud de corrección de señal",
        "area": "CMD",
        "type": "Solicitud de intervención",
        "subtype": "Corrección",
        "body": "Solicitar corrección de una señal, indicación, comando o analógica.",
        "schema": schema(
            field("Señal afectada", placeholder="Nombre CMD / tag / punto"),
            field("Equipo / instalación", placeholder="ET, RTU, alimentador, línea"),
            field("Tipo de señal", "select", options=["Digital", "Analógica", "Comando", "Alarma", "Otro"]),
            field("Comportamiento observado", "textarea"),
            field("Comportamiento esperado", "textarea"),
            field("Prioridad operativa", "select", required=False, options=["Baja", "Normal", "Alta", "Urgente"]),
        ),
    },
    {
        "name": "Solicitud de revisión de comunicación",
        "area": "Comunicaciones",
        "type": "Solicitud de intervención",
        "subtype": "Revisión",
        "body": "Solicitar revisión de enlace, comunicación, ruta o equipo de comunicaciones.",
        "schema": schema(
            field("Equipo / RTU"),
            field("Sitio / estación"),
            field("Síntoma", "textarea", placeholder="Intermitencia, sin enlace, pérdida de paquetes, etc."),
            field("Desde cuándo ocurre", "text", required=False),
            field("Pruebas ya realizadas", "textarea", required=False),
        ),
    },
    {
        "name": "Solicitud de asistencia técnica",
        "area": "Telecontrol",
        "type": "Solicitud de intervención",
        "subtype": "Asistencia",
        "body": "Solicitar asistencia técnica a un área.",
        "schema": schema(
            field("Necesidad", "textarea"),
            field("Sistema / equipo"),
            field("Fecha requerida", "date", required=False),
            field("Contacto operativo", required=False),
        ),
    },
    {
        "name": "Plantilla base genérica",
        "area": "Telecontrol",
        "type": "Solicitud de intervención",
        "subtype": "Otro",
        "body": "Plantilla simple para casos no contemplados.",
        "schema": schema(
            field("Detalle", "textarea"),
            field("Impacto", "textarea", required=False),
            field("Acción solicitada", "textarea"),
        ),
    },
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
    legacy_scada = session.query(Area).filter_by(name="SCADA").first()
    existing_cmd = session.query(Area).filter_by(name="CMD").first()
    if legacy_scada and not existing_cmd:
        legacy_scada.name = "CMD"
        session.flush()
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
            admin = User(username=admin_username, full_name=admin_name, gmail=admin_email, main_area=areas["Telecontrol"], active=True)
            admin.set_password(admin_password)
            session.add(admin)
        admin.roles = [session.query(Role).filter_by(name="Administrador").one()]
        admin.visible_areas = list(areas.values())

    for item in TEMPLATES:
        template = session.query(TicketTemplate).filter_by(name=item["name"]).first()
        if not template:
            session.add(TicketTemplate(name=item["name"], area=areas[item["area"]], suggested_type=item["type"], suggested_subtype=item["subtype"], body=item["body"], schema_json=item["schema"], active=True))
        elif not template.schema_json or not (template.schema_json.get("fields") if isinstance(template.schema_json, dict) else None):
            template.schema_json = item["schema"]
            template.body = item["body"]
