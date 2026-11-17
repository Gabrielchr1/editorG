#!/usr/bin/env bash
set -euo pipefail

# Instalador / Atualizador Rápido - EditorGráfica Pro (Ubuntu / Debian VPS)
REPO_URL="${REPO_URL:-https://github.com/Gabrielchr1/editorG.git}"
APP_DIR="${APP_DIR:-/opt/editorgrafica}"
APP_PORT="${APP_PORT:-8000}"
SERVER_NAME="${SERVER_NAME:-_}"
SERVICE_NAME="editorgrafica"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Por favor, execute como root ou com sudo: sudo bash deploy_vps.sh"
  exit 1
fi

echo "==> [1/6] Instalando dependências do sistema (Python, Git, Nginx, Fontes TrueType)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx fonts-liberation fonts-dejavu-core curl

echo "==> [2/6] Obtendo código-fonte em ${APP_DIR}..."
if [ -d "${APP_DIR}/.git" ]; then
  git -C "${APP_DIR}" fetch --all --prune
  git -C "${APP_DIR}" pull --ff-only origin main
else
  mkdir -p "${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"
mkdir -p uploads

echo "==> [3/6] Configurando ambiente virtual Python e dependências..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "==> [4/6] Aplicando migrações e dados iniciais do SQLite..."
.venv/bin/python -c "from backend.database import run_migrations, SessionLocal; from backend.seed_data import seed_initial_data; run_migrations(); db=SessionLocal(); seed_initial_data(db); db.close()"

echo "==> [5/6] Configurando serviço systemd (${SERVICE_NAME})..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=EditorGrafica Pro - Plataforma de Miolos de Agendas CMYK
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${APP_DIR}/.venv/bin/uvicorn main:app --host 127.0.0.1 --port ${APP_PORT} --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "==> [6/6] Configurando proxy reverso Nginx (porta 80 -> ${APP_PORT})..."
cat > "/etc/nginx/sites-available/${SERVICE_NAME}" <<EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
if [ -L /etc/nginx/sites-enabled/default ]; then
  rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl enable nginx
systemctl restart nginx

PUBLIC_IP="$(curl -s --max-time 3 https://api.ipify.org || hostname -I | awk '{print $1}')"
echo ""
echo "=========================================================="
echo " EditorGrafica Pro instalado e em execucao na VPS!"
echo " Acesse: http://${PUBLIC_IP}"
echo " Status: systemctl status ${SERVICE_NAME}"
echo " Logs:   journalctl -u ${SERVICE_NAME} -f"
echo "=========================================================="
