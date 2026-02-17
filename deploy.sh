#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-cibics}"
REPO_URL="${REPO_URL:-https://github.com/myphoneme/cibics.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/home/project/cibics}"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8200}"
API_PREFIX="${API_PREFIX:-/api/v1}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_NAME="${SERVICE_NAME:-${APP_NAME}-backend}"
FRONTEND_SERVICE_NAME="${FRONTEND_SERVICE_NAME:-}"

# Optional: set to 1 if you want npm install instead of npm ci when lockfile exists.
NPM_FORCE_INSTALL="${NPM_FORCE_INSTALL:-0}"

COLOR_BLUE='\033[1;34m'
COLOR_GREEN='\033[1;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[1;31m'
COLOR_RESET='\033[0m'

step() {
  printf "\n${COLOR_BLUE}========== %s ==========${COLOR_RESET}\n" "$*"
}

info() {
  printf "[INFO] %s\n" "$*"
}

ok() {
  printf "${COLOR_GREEN}[OK]${COLOR_RESET} %s\n" "$*"
}

warn() {
  printf "${COLOR_YELLOW}[WARN]${COLOR_RESET} %s\n" "$*"
}

fail() {
  printf "${COLOR_RED}[ERROR]${COLOR_RESET} %s\n" "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this script as root: sudo bash deploy.sh"
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

assert_commands() {
  step "Validating Required Commands"
  command_exists git || fail "git not found"
  command_exists systemctl || fail "systemctl not found"
  command_exists node || fail "node not found"
  command_exists npm || fail "npm not found"

  if [[ "${PYTHON_BIN}" == "python3" ]] && command_exists python3.11; then
    PYTHON_BIN="python3.11"
    info "Detected python3.11. Using PYTHON_BIN=${PYTHON_BIN}"
  fi

  command_exists "${PYTHON_BIN}" || fail "${PYTHON_BIN} not found"
  ok "All required commands are available"
}

sync_repo() {
  step "Fetching Latest Code From GitHub"

  if [[ -d "${APP_DIR}/.git" ]]; then
    info "Repository exists at ${APP_DIR}"
    git -C "${APP_DIR}" remote set-url origin "${REPO_URL}"
    git -C "${APP_DIR}" fetch --all --prune
    git -C "${APP_DIR}" checkout "${BRANCH}"
    git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
  else
    info "Repository not found locally. Cloning ${REPO_URL}"
    mkdir -p "$(dirname "${APP_DIR}")"
    git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
  fi

  local latest_commit
  latest_commit="$(git -C "${APP_DIR}" rev-parse --short HEAD)"
  ok "Code synced successfully. Current commit: ${latest_commit}"
}

update_backend() {
  step "Updating Backend Dependencies"
  cd "${BACKEND_DIR}"

  if [[ ! -f .env ]]; then
    fail "Missing ${BACKEND_DIR}/.env"
  fi

  if [[ ! -d venv ]]; then
    info "Creating backend virtual environment"
    "${PYTHON_BIN}" -m venv venv
  fi

  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate

  ok "Backend dependencies installed successfully"

  step "Restarting Backend Service"
  systemctl restart "${SERVICE_NAME}"

  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "Backend service is running: ${SERVICE_NAME}"
  else
    systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,30p'
    fail "Backend service failed to start: ${SERVICE_NAME}"
  fi

  info "Backend status preview:"
  systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,12p'
}

update_frontend() {
  step "Updating Frontend Dependencies"
  cd "${FRONTEND_DIR}"

  if [[ -f package-lock.json && "${NPM_FORCE_INSTALL}" != "1" ]]; then
    npm ci
  else
    npm install
  fi

  ok "Frontend dependencies installed successfully"

  step "Building Frontend"
  VITE_API_URL="${VITE_API_URL:-${API_PREFIX}}" npm run build
  ok "Frontend build completed"

  if [[ -n "${FRONTEND_SERVICE_NAME}" ]]; then
    step "Restarting Frontend Service"
    systemctl restart "${FRONTEND_SERVICE_NAME}"
    if systemctl is-active --quiet "${FRONTEND_SERVICE_NAME}"; then
      ok "Frontend service is running: ${FRONTEND_SERVICE_NAME}"
    else
      systemctl --no-pager --full status "${FRONTEND_SERVICE_NAME}" | sed -n '1,30p'
      fail "Frontend service failed to start: ${FRONTEND_SERVICE_NAME}"
    fi
  else
    info "No FRONTEND_SERVICE_NAME provided. Frontend build is updated on disk only."
  fi
}

health_check() {
  step "Verifying Backend Health"

  if ! command_exists curl; then
    warn "curl not found. Skipping health check."
    return
  fi

  local url="http://${BACKEND_HOST}:${BACKEND_PORT}${API_PREFIX}/health"
  local ok_health=0

  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null; then
      ok_health=1
      break
    fi
    sleep 1
  done

  if [[ "${ok_health}" -eq 1 ]]; then
    ok "Health check passed: ${url}"
  else
    fail "Health check failed: ${url}"
  fi
}

summary() {
  step "Deployment Update Complete"
  printf "Application: %s\n" "${APP_NAME}"
  printf "Branch: %s\n" "${BRANCH}"
  printf "Backend service: %s\n" "${SERVICE_NAME}"
  if [[ -n "${FRONTEND_SERVICE_NAME}" ]]; then
    printf "Frontend service: %s\n" "${FRONTEND_SERVICE_NAME}"
  else
    printf "Frontend: static build updated (web server unchanged)\n"
  fi
  printf "Path: %s\n" "${APP_DIR}"
}

main() {
  require_root
  assert_commands
  sync_repo
  update_backend
  update_frontend
  health_check
  summary
}

main "$@"
