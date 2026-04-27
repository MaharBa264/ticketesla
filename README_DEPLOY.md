# Despliegue Ticketesla

Estructura sugerida:

```text
/opt/ticketesla/
  .env
  deploy.sh
  rollback.sh
  releases/
  current -> releases/YYYY-MM-DD-HHMM
  instance/
  logs/
  storage/
  backups/
```

## Preparar servidor

```bash
sudo mkdir -p /opt/ticketesla/{releases,instance,logs,storage,backups}
sudo cp .env.example /opt/ticketesla/.env
sudo nano /opt/ticketesla/.env
```

Crear usuario y base PostgreSQL:

```sql
CREATE USER ticketesla WITH PASSWORD 'ticketesla';
CREATE DATABASE ticketesla OWNER ticketesla;
```

Instalar servicio y Nginx:

```bash
sudo cp deploy/ticketesla.service.example /etc/systemd/system/ticketesla.service
sudo systemctl daemon-reload
sudo systemctl enable ticketesla
sudo cp deploy/nginx-ticketesla.conf.example /etc/nginx/sites-available/ticketesla
sudo ln -s /etc/nginx/sites-available/ticketesla /etc/nginx/sites-enabled/ticketesla
sudo nginx -t && sudo systemctl reload nginx
```

## Deploy

```bash
sudo cp deploy.sh rollback.sh /opt/ticketesla/
cd /opt/ticketesla
sudo REPO_URL=https://github.com/tu-org/ticketesla.git BRANCH=main ./deploy.sh
```

## Rollback

```bash
cd /opt/ticketesla
sudo ./rollback.sh
sudo ./rollback.sh /opt/ticketesla/releases/2026-04-24-1345
```
