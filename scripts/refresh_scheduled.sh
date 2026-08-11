#!/usr/bin/env bash
# Weekly/server cron entrypoint: sync III_db_final, rebuild CSVs + Parquet, optional API restart.
#
# Usage:
#   ./scripts/refresh_scheduled.sh
#   FASTPHENO_SERVICE_NAME=fastpheno ./scripts/refresh_scheduled.sh
#
# Env (optional):
#   FASTPHENO_LOG_DIR       log directory (default: <repo>/logs)
#   FASTPHENO_PYTHON        python binary if .venv is absent
#   FASTPHENO_SERVICE_NAME  systemd unit to restart after a successful refresh
#   FASTPHENO_SKIP_RESTART  set to 1 to skip service restart

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${FASTPHENO_LOG_DIR:-$ROOT/logs}"
LOCK_DIR="$LOG_DIR/refresh.lock.d"
LOG_FILE="$LOG_DIR/refresh.log"
mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf '%s refresh already running; skipping\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" >>"$LOG_FILE"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PY="$ROOT/.venv/bin/python3"
else
  PY="${FASTPHENO_PYTHON:-python3}"
fi

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

restart_api() {
  if [[ "${FASTPHENO_SKIP_RESTART:-0}" == "1" ]]; then
    log "skip restart (FASTPHENO_SKIP_RESTART=1)"
    return 0
  fi
  local service="${FASTPHENO_SERVICE_NAME:-fastpheno}"
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet "$service" 2>/dev/null; then
      if systemctl restart "$service"; then
        log "restarted systemd service: $service"
        return 0
      fi
      log "warning: systemctl restart failed for $service"
      return 1
    fi
  fi
  log "no running API service to restart (set FASTPHENO_SERVICE_NAME if needed)"
  return 0
}

{
  log "=== refresh start (root=$ROOT) ==="
  log "python: $PY ($("$PY" --version 2>&1))"

  if [[ ! -f "$ROOT/backend/.env" ]]; then
    log "error: backend/.env not found; copy backend/.env.example and fill in remote credentials"
    exit 1
  fi

  "$PY" "$ROOT/scripts/refresh_from_remote.py"
  log "refresh_from_remote.py finished OK"

  restart_api || true
  log "=== refresh complete ==="
} >>"$LOG_FILE" 2>&1
