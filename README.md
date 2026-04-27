# Ticketesla

Sistema interno independiente de tickets técnicos para Comunicaciones, Protecciones, Telecontrol y SCADA.

## DEV

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Crear una base PostgreSQL local y ajustar `DATABASE_URL` en `.env`, por ejemplo `postgresql+psycopg://ticketesla:ticketesla@localhost:5432/ticketesla`.

```bash
set FLASK_APP=manage.py
flask db upgrade
flask seed
flask run
```

La interfaz usa hora local `America/Argentina/San_Luis` y formato `DD/MM/AAAA HH:MM:SS`.

## Base inicial

El comando `flask seed` crea áreas, permisos, roles, plantillas iniciales y el administrador si existen:

- `TICKETESLA_ADMIN_USERNAME`
- `TICKETESLA_ADMIN_PASSWORD`
- `TICKETESLA_ADMIN_EMAIL`
- `TICKETESLA_ADMIN_NAME`

## GitHub

```bash
git add .
git commit -m "Initial Ticketesla MVP"
git remote add origin https://github.com/tu-org/ticketesla.git
git push -u origin main
```

## API

La API base vive en `/api/v1` e incluye login, logout, usuario actual, tickets, comentarios, reconocimiento, resolución y derivación.
