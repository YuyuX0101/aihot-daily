#!/usr/bin/env bash
# Portable catch-up wrapper (Beijing time). DEFAULT: refuse to run live work.
# Parent must set AIHOT_ENABLE_SCHEDULE=1 AND AIHOT_DRY_RUN=0 for real cutover.
# Still requires AIHOT_FEISHU_ENABLED / AIHOT_ALLOW_GIT_PUSH for outbound effects.
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${AIHOT_ENV_FILE:-}" && -f "${AIHOT_ENV_FILE}" ]]; then
  set -a; source "${AIHOT_ENV_FILE}"; set +a
elif [[ -n "${AIHOT_HOME:-}" && -f "${AIHOT_HOME}/config/aihot.env" ]]; then
  set -a; source "${AIHOT_HOME}/config/aihot.env"; set +a
fi

LOG_DIR="${AIHOT_LOG_DIR:-$ROOT/logs}"
LOCK_DIR="${AIHOT_LOCK_DIR:-$ROOT/logs/locks}"
mkdir -p "$LOG_DIR" "$LOCK_DIR"

NOW_HMS="$(date +%H:%M:%S)"
if [[ "$NOW_HMS" < "12:00:00" ]]; then
  echo "[run-if-missed] before 12:00 Asia/Shanghai — skip"
  exit 0
fi

STAMP="$LOG_DIR/.last-run-date"
TODAY="$(date +%Y-%m-%d)"
if [[ -f "$STAMP" ]] && [[ "$(tr -d ' \r\n' < "$STAMP")" == "$TODAY" ]]; then
  echo "[run-if-missed] already ran $TODAY — skip"
  exit 0
fi

if [[ "${AIHOT_ENABLE_SCHEDULE:-0}" != "1" ]]; then
  echo "[run-if-missed] AIHOT_ENABLE_SCHEDULE!=1 — refusing to execute (safe default)."
  echo "[run-if-missed] This does NOT mark the day complete."
  exit 0
fi

LOCK="$LOCK_DIR/unified.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[run-if-missed] lock busy — another run in progress"
  exit 0
fi

# Even with schedule enabled, default dry-run unless explicitly cleared.
DRY="${AIHOT_DRY_RUN:-1}"
TARGET="$(date -d 'yesterday' +%Y-%m-%d)"
LOG="$LOG_DIR/scheduled-$TODAY.log"
{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] start target=$TARGET dry_run=$DRY"
  if [[ "$DRY" == "1" ]]; then
    python3 -m tools.aihot_pipeline run --date "$TARGET" --skip-aihot || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] dry-run finished (no stamp write for dry-run-only schedule probe)"
    exit 0
  fi
  # Live path — still gated by git/feishu env flags inside Python.
  RUN_ARGS=(run --date "$TARGET")
  if [[ -n "${AIHOT_GROUPS_FILE:-}" ]]; then
    RUN_ARGS+=(--groups-file "$AIHOT_GROUPS_FILE")
  else
    RUN_ARGS+=(--skip-aihot)
  fi
  set +e
  python3 -m tools.aihot_pipeline "${RUN_ARGS[@]}"
  rc=$?
  set -e
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] end rc=$rc"
  if [[ $rc -eq 0 ]]; then
    printf '%s\n' "$TODAY" > "$STAMP"
  fi
  exit $rc
} >>"$LOG" 2>&1
