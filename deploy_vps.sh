#!/usr/bin/env bash
set -euo pipefail

# Uso:
#   sudo bash deploy_vps.sh "https://provedor/get.php?username=USUARIO&password=SENHA&type=m3u_plus&output=ts" "USUARIO" "SENHA" "http://host:80" "meudominio.com" "8000"
#
# Se o domínio for vazio, o Nginx roda em http://IP:80 sem HTTPS.
# O script cria o .env automaticamente com as credenciais informadas.

IPTV_URL="${1:-}"
IPTV_USERNAME="${2:-}"
IPTV_PASSWORD="${3:-}"
IPTV_HOST="${4:-http://kixar.xyz:80}"
DOMAIN="${5:-}"
PORT="${6:-8000}"
APP_DIR="/opt/iptv-server"
USER_NAME="iptv"
SYSTEM_SERVICE="iptv"

if [[ -z "$IPTV_URL" || -z "$IPTV_USERNAME" || -z "$IPTV_PASSWORD" ]]; then
  echo "Uso: sudo bash deploy_vps.sh \"IPTV_URL\" \"IPTV_USERNAME\" \"IPTV_PASSWORD\" \"IPTV_HOST\" \"DOMAIN\" \"PORT\""
  echo "Exemplo: sudo bash deploy_vps.sh \"https://site.com/get.php?username=USER&password=PASS&type=m3u_plus&output=ts\" \"USER\" \"PASS\" \"http://site.com:80\" \"api.example.com\" \"8000\""
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Execute como root: sudo bash deploy_vps.sh ..."
  exit 1
fi

echo "[1/9] Atualizando sistema..."
apt-get update
apt-get upgrade -y

echo "[2/9] Instalando dependências..."
apt-get install -y python3 python3-venv python3-pip git nginx ufw ca-certificates curl certbot python3-certbot-nginx

if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$USER_NAME"
fi

if [[ ! -d "$APP_DIR" ]]; then
  mkdir -p "$APP_DIR"
fi

if [[ -d "$APP_DIR/.git" ]]; then
  echo "[3/9] Atualizando repositório existente..."
  git -C "$APP_DIR" pull origin main || git -C "$APP_DIR" fetch origin && git -C "$APP_DIR" reset --hard origin/main
else
  echo "[3/9] Clonando repositório..."
  git clone https://github.com/copa-bhs/servervenuscine.git "$APP_DIR"
  git -C "$APP_DIR" checkout main || true
fi

chown -R "$USER_NAME:$USER_NAME" "$APP_DIR"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  echo "[4/9] Criando ambiente virtual Python..."
  python3 -m venv "$APP_DIR/.venv"
fi

echo "[5/9] Instalando dependências Python..."
su -s /bin/bash "$USER_NAME" -c "cd '$APP_DIR' && . .venv/bin/activate && pip install -r requirements.txt"

cat > "$APP_DIR/.env" <<EOF
IPTV_URL=${IPTV_URL}
IPTV_USERNAME=${IPTV_USERNAME}
IPTV_PASSWORD=${IPTV_PASSWORD}
IPTV_HOST=${IPTV_HOST}
USER_AGENT=VLC/3.0.20 LibVLC/3.0.20
CACHE_TTL=3600
PORT=${PORT}
EOF

chown "$USER_NAME:$USER_NAME" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

cat > "/etc/systemd/system/${SYSTEM_SERVICE}.service" <<EOF
[Unit]
Description=IPTV Organizer Pro
After=network.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

if [[ -n "$DOMAIN" ]]; then
  echo "[6/9] Configurando Nginx para domínio: ${DOMAIN}"
  cat > "/etc/nginx/sites-available/iptv" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  ln -sf /etc/nginx/sites-available/iptv /etc/nginx/sites-enabled/iptv
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx

  echo "[7/9] Obtendo certificado HTTPS com Certbot..."
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN" || true
else
  echo "[6/9] Configurando Nginx em HTTP simples..."
  cat > "/etc/nginx/sites-available/iptv" <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  ln -sf /etc/nginx/sites-available/iptv /etc/nginx/sites-enabled/iptv
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx
fi

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable || true

echo "[8/9] Iniciando serviço..."
systemctl enable "$SYSTEM_SERVICE"
systemctl restart "$SYSTEM_SERVICE"
systemctl status "$SYSTEM_SERVICE" --no-pager || true

echo "[9/9] Verificando resposta rápida..."
sleep 5
curl -fsS "http://127.0.0.1:${PORT}/status" || echo "A API ainda não respondeu em localhost:${PORT}. Verifique logs com: journalctl -u ${SYSTEM_SERVICE} -f"

if [[ -n "$DOMAIN" ]]; then
  echo ""
  echo "✅ Deploy concluído."
  echo "URL HTTP: http://${DOMAIN}"
  echo "URL HTTPS: https://${DOMAIN}"
else
  echo ""
  echo "✅ Deploy concluído em HTTP."
  echo "URL: http://$(hostname -I | awk '{print $1}'):80"
fi

echo ""
echo "Arquivos importantes:"
echo "- .env: ${APP_DIR}/.env"
echo "- serviço: /etc/systemd/system/${SYSTEM_SERVICE}.service"
echo "- logs: journalctl -u ${SYSTEM_SERVICE} -f"
