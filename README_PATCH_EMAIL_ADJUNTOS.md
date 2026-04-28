# Parche Ticketesla: email Office 365, reapertura y adjuntos

Archivos incluidos:

- `app/services/email_service.py`: servicio SMTP configurable por `.env`, con `EMAIL_ENABLED`, `EMAIL_DRY_RUN`, `EMAIL_DEBUG_TO`, `BASE_URL` y variables SMTP.
- `app/services/notification_service.py`: notifica ticket nuevo, derivado, resuelto y reabierto. Usa `corporate_email`, no Gmail.
- `app/services/ticket_service.py`: agrega notificación de reapertura, endurece derivación y mejora guardado de adjuntos.
- `app/blueprints/tickets/routes.py`: evita que un error de adjunto rompa la creación del ticket; muestra mensajes claros.
- `app/config.py`: agrega configuración de email y extensiones permitidas.
- `.env.example`: agrega variables de Office 365 SMTP y adjuntos.

## Configuración recomendada para prueba sin envío real

```env
EMAIL_ENABLED=true
EMAIL_DRY_RUN=true
EMAIL_BACKEND=smtp
BASE_URL=http://172.17.1.170:8082
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=10
SMTP_FROM=Ticketesla <ticketesla@edesal.com.ar>
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_DEBUG_TO=
```

Con `EMAIL_DRY_RUN=true`, Ticketesla no envía emails reales; solo registra en logs lo que habría enviado.

## Configuración real cuando TI entregue la casilla

```env
EMAIL_ENABLED=true
EMAIL_DRY_RUN=false
EMAIL_BACKEND=smtp
BASE_URL=http://172.17.1.170:8082
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=10
SMTP_FROM=Ticketesla <ticketesla@edesal.com.ar>
SMTP_USERNAME=ticketesla@edesal.com.ar
SMTP_PASSWORD=CLAVE_O_TOKEN_DE_LA_CASILLA
EMAIL_DEBUG_TO=
```

Para pruebas reales, puede usarse:

```env
EMAIL_DEBUG_TO=amedina@edesal.com.ar
```

Así todas las notificaciones salen solo hacia esa casilla.

## Después de aplicar

```bash
grep -RIn "Ã\|Â\|â" app/templates app/static app/blueprints app/services app/models scripts
python -m py_compile app/services/email_service.py app/services/notification_service.py app/services/ticket_service.py app/blueprints/tickets/routes.py app/config.py
sudo systemctl restart ticketesla
sudo journalctl -u ticketesla -f
```
