#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-cibics}"
DOMAIN="${DOMAIN:-cibics.phoneme.in}"
REPO_URL="${REPO_URL:-https://github.com/myphoneme/cibics.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/home/project/cibics}"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8200}"
API_PREFIX="${API_PREFIX:-/api/v1}"

RUN_USER="${RUN_USER:-project}"
RUN_GROUP="${RUN_GROUP:-${RUN_USER}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MIN_NODE_MAJOR=18

SERVICE_NAME="${APP_NAME}-backend"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
NGINX_CONF="/etc/nginx/conf.d/${APP_NAME}.conf"

SSL_CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
SSL_KEY_PATH="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"

DB_HOST="${DB_HOST:-10.100.60.113}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-cibics}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-indian@123}"

DEFAULT_SUPER_ADMIN_NAME="${DEFAULT_SUPER_ADMIN_NAME:-Super Admin}"
DEFAULT_SUPER_ADMIN_EMAIL="${DEFAULT_SUPER_ADMIN_EMAIL:-admin@cibics.local}"
DEFAULT_SUPER_ADMIN_PASSWORD="${DEFAULT_SUPER_ADMIN_PASSWORD:-Admin@123}"
DEFAULT_ASSIGNEE_PASSWORD="${DEFAULT_ASSIGNEE_PASSWORD:-Assignee@123}"

ALLOWED_ORIGINS_VALUE="[\"https://${DOMAIN}\",\"http://${DOMAIN}\",\"http://localhost:3100\",\"http://127.0.0.1:3100\"]"

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy][error] %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this script as root (sudo bash deploy.sh)."
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

install_dependencies() {
  local pkg_manager=""
  if command_exists dnf; then
    pkg_manager="dnf"
  elif command_exists yum; then
    pkg_manager="yum"
  else
    fail "Neither dnf nor yum was found. Install dependencies manually."
  fi

  log "Installing base dependencies using ${pkg_manager}."
  "${pkg_manager}" install -y git nginx "${PYTHON_BIN}" python3-pip nodejs npm curl
}

check_node_version() {
  local node_major
  node_major="$(node -p "process.versions.node.split('.')[0]")"
  if (( node_major < MIN_NODE_MAJOR )); then
    fail "Node.js ${MIN_NODE_MAJOR}+ is required. Found: $(node -v)."
  fi
}

resolve_run_user() {
  if ! id -u "${RUN_USER}" >/dev/null 2>&1; then
    log "User '${RUN_USER}' does not exist. Falling back to root for systemd service."
    RUN_USER="root"
    RUN_GROUP="root"
  fi
}

run_as_postgres() {
  if command_exists runuser; then
    runuser -u postgres -- "$@"
  else
    su - postgres -c "$*"
  fi
}

sync_repo() {
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "Updating repository in ${APP_DIR}."
    git -C "${APP_DIR}" fetch --all --prune
    git -C "${APP_DIR}" checkout "${BRANCH}"
    git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
  else
    log "Cloning repository into ${APP_DIR}."
    mkdir -p "$(dirname "${APP_DIR}")"
    git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
  fi
}

set_env_force() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -qE "^${key}=" "${file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${file}"
  fi
}

set_env_default() {
  local key="$1"
  local value="$2"
  local file="$3"
  if ! grep -qE "^${key}=" "${file}"; then
    printf '%s=%s\n' "${key}" "${value}" >>"${file}"
  fi
}

ensure_secret_key() {
  local file="$1"
  local current=""
  current="$(grep -E '^SECRET_KEY=' "${file}" | head -n1 | cut -d= -f2- || true)"

  if [[ -z "${current}" || "${current}" == "replace-with-strong-secret" || "${current}" == "change-me-in-env" ]]; then
    local generated=""
    if command_exists openssl; then
      generated="$(openssl rand -hex 32)"
    else
      generated="$("${PYTHON_BIN}" - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
    fi
    set_env_force "SECRET_KEY" "${generated}" "${file}"
    log "Generated a new SECRET_KEY in ${file}."
  fi
}

ensure_database() {
  if ! command_exists psql; then
    log "psql not found. Skipping automatic database creation."
    return
  fi

  if [[ "${DB_HOST}" != "localhost" && "${DB_HOST}" != "127.0.0.1" ]]; then
    log "DB_HOST is ${DB_HOST}; skipping local database creation."
    return
  fi

  if ! id -u postgres >/dev/null 2>&1; then
    log "postgres OS user not found. Skipping automatic database creation."
    return
  fi

  if run_as_postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    log "Database '${DB_NAME}' already exists."
  else
    log "Creating PostgreSQL database '${DB_NAME}'."
    run_as_postgres createdb "${DB_NAME}"
  fi
}

setup_backend() {
  log "Setting up backend."
  cd "${BACKEND_DIR}"

  if [[ ! -f .env ]]; then
    cp .env.example .env
    log "Created backend/.env from .env.example."
  fi

  set_env_force "APP_NAME" "Cibics Tracking API" .env
  set_env_force "API_V1_PREFIX" "${API_PREFIX}" .env
  set_env_force "API_PORT" "${BACKEND_PORT}" .env
  set_env_force "ALLOWED_ORIGINS" "${ALLOWED_ORIGINS_VALUE}" .env

  set_env_default "DB_HOST" "${DB_HOST}" .env
  set_env_default "DB_PORT" "${DB_PORT}" .env
  set_env_default "DB_NAME" "${DB_NAME}" .env
  set_env_default "DB_USER" "${DB_USER}" .env
  set_env_default "DB_PASSWORD" "${DB_PASSWORD}" .env

  set_env_default "DEFAULT_SUPER_ADMIN_NAME" "${DEFAULT_SUPER_ADMIN_NAME}" .env
  set_env_default "DEFAULT_SUPER_ADMIN_EMAIL" "${DEFAULT_SUPER_ADMIN_EMAIL}" .env
  set_env_default "DEFAULT_SUPER_ADMIN_PASSWORD" "${DEFAULT_SUPER_ADMIN_PASSWORD}" .env
  set_env_default "DEFAULT_ASSIGNEE_PASSWORD" "${DEFAULT_ASSIGNEE_PASSWORD}" .env

  ensure_secret_key .env

  if [[ ! -d venv ]]; then
    "${PYTHON_BIN}" -m venv venv
  fi

  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
}

setup_frontend() {
  log "Building frontend."
  cd "${FRONTEND_DIR}"

  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi

  VITE_API_URL="${API_PREFIX}" npm run build
}

write_systemd_service() {
  log "Configuring systemd service: ${SERVICE_NAME}."
  cat >"${SERVICE_FILE}" <<EOF
[Unit]
Description=Cibics FastAPI Backend
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=${BACKEND_DIR}/venv/bin/uvicorn app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"
}

write_nginx_conf_http_only() {
  cat >"${NGINX_CONF}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        root ${FRONTEND_DIR}/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
}

write_nginx_conf_ssl() {
  cat >"${NGINX_CONF}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate ${SSL_CERT_PATH};
    ssl_certificate_key ${SSL_KEY_PATH};

    location / {
        root ${FRONTEND_DIR}/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
}

setup_nginx() {
  log "Configuring nginx for ${DOMAIN}."

  if [[ -f "${SSL_CERT_PATH}" && -f "${SSL_KEY_PATH}" ]]; then
    write_nginx_conf_ssl
  else
    log "SSL certificate not found at ${SSL_CERT_PATH}. Writing HTTP-only config."
    write_nginx_conf_http_only
  fi

  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
}

verify_services() {
  log "Verifying backend health endpoint."
  curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null

  log "Backend service status:"
  systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,8p'

  log "Deployment complete."
  if [[ -f "${SSL_CERT_PATH}" && -f "${SSL_KEY_PATH}" ]]; then
    printf '\nOpen: https://%s\n' "${DOMAIN}"
  else
    printf '\nOpen: http://%s\n' "${DOMAIN}"
    printf 'SSL cert not found. Add certs, then rerun deploy.sh to enable HTTPS config.\n'
  fi
}

main() {
  require_root
  install_dependencies

  command_exists git || fail "git not found."
  command_exists "${PYTHON_BIN}" || fail "${PYTHON_BIN} not found."
  command_exists pip3 || fail "pip3 not found."
  command_exists node || fail "node not found."
  command_exists npm || fail "npm not found."
  command_exists systemctl || fail "systemctl not found."
  command_exists nginx || fail "nginx not found."
  command_exists curl || fail "curl not found."

  check_node_version
  resolve_run_user

  sync_repo
  ensure_database
  setup_backend
  setup_frontend
  write_systemd_service
  setup_nginx
  verify_services
}

main "$@"
