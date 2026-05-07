#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ticketesla}"
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
SERVICE="${SERVICE:-ticketesla.service}"
BIND_URL="${BIND_URL:-http://127.0.0.1:8020/health}"

if [ -z "$REPO_URL" ]; then
  echo "Definí REPO_URL=https://github.com/MaharBa264/ticketesla.git"
  exit 1
fi

timestamp="$(date +%Y-%m-%d-%H%M)"
release="$APP_DIR/releases/$timestamp"
mkdir -p "$APP_DIR/releases" "$APP_DIR/logs" "$APP_DIR/storage" "$APP_DIR/instance" "$APP_DIR/backups"
git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$release"
ln -sfn "$APP_DIR/.env" "$release/.env"
ln -sfn "$APP_DIR/storage" "$release/storage"
ln -sfn "$APP_DIR/instance" "$release/instance"
PYTHON_BIN="${PYTHON_BIN:-/opt/ticketesla/.venv/bin/python}"
"$PYTHON_BIN" -m venv "$release/.venv"
"$release/.venv/bin/pip" install --upgrade pip
"$release/.venv/bin/pip" install -r "$release/requirements.txt"
cd "$release"
export RELEASE_VERSION="$timestamp"
"$release/.venv/bin/flask" db upgrade
if "$release/.venv/bin/flask" --help | grep -q "  seed"; then
  "$release/.venv/bin/flask" seed
else
  echo "No existe comando flask seed; se omite seed."
fi
ln -sfn "$release" "$APP_DIR/current"
systemctl restart "$SERVICE"
sleep 2
curl -fsS "$BIND_URL"
echo "Deploy OK: $timestamp"
