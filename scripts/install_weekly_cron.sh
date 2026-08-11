#!/usr/bin/env bash
# Install a weekly cron job for scripts/refresh_scheduled.sh (Sunday 02:00 local time).
#
# Usage:
#   ./scripts/install_weekly_cron.sh
#   ./scripts/install_weekly_cron.sh --uninstall
#   CRON_SCHEDULE='0 3 * * 1' ./scripts/install_weekly_cron.sh   # Monday 03:00

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFRESH_SCRIPT="$ROOT/scripts/refresh_scheduled.sh"
MARKER="# fastpheno-dashboard weekly data refresh"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 2 * * 0}"
UNINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --uninstall) UNINSTALL=1 ;;
    -h|--help)
      echo "Usage: $0 [--uninstall]"
      echo "  Installs: $CRON_SCHEDULE $REFRESH_SCRIPT"
      echo "  Override schedule: CRON_SCHEDULE='0 3 * * 1' $0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "$REFRESH_SCRIPT" ]]; then
  chmod +x "$REFRESH_SCRIPT"
fi

CRON_LINE="$CRON_SCHEDULE $REFRESH_SCRIPT $MARKER"

existing="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "$existing" | grep -Fv "$MARKER" | grep -Fv "$REFRESH_SCRIPT" || true)"

if [[ "$UNINSTALL" == "1" ]]; then
  if [[ -n "$filtered" ]]; then
    printf '%s\n' "$filtered" | crontab -
  else
    crontab -r 2>/dev/null || true
  fi
  echo "Removed fastpheno weekly cron job."
  exit 0
fi

{
  if [[ -n "$filtered" ]]; then
    printf '%s\n' "$filtered"
  fi
  echo "$CRON_LINE"
} | crontab -

echo "Installed weekly cron job:"
echo "  $CRON_LINE"
echo ""
echo "Logs: ${FASTPHENO_LOG_DIR:-$ROOT/logs}/refresh.log"
echo "Test now: $REFRESH_SCRIPT"
echo "Remove:   $0 --uninstall"
