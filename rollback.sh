#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ticketesla}"
SERVICE="${SERVICE:-ticketesla.service}"
BIND_URL="${BIND_URL:-http://127.0.0.1:8020/health}"
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  current="$(readlink -f "$APP_DIR/current" || true)"
  TARGET="$(find "$APP_DIR/releases" -mindepth 1 -maxdepth 1 -type d | sort | grep -v "$current" | tail -n 1)"
fi

if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "No se encontró una release para rollback."
  exit 1
fi

ln -sfn "$TARGET" "$APP_DIR/current"
systemctl restart "$SERVICE"
sleep 2
curl -fsS "$BIND_URL"
echo "Rollback OK: $TARGET"
