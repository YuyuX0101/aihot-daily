#!/usr/bin/env bash
# Manual dry-run of unified pipeline on parent host. Never enables timers.
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${AIHOT_ENV_FILE:-${AIHOT_HOME:-}/config/aihot.env}"
if [[ -n "${AIHOT_HOME:-}" && -f "${AIHOT_HOME}/config/aihot.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "${AIHOT_HOME}/config/aihot.env"; set +a
elif [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

export AIHOT_DRY_RUN=1
export AIHOT_FEISHU_ENABLED=0
export AIHOT_ALLOW_GIT_PUSH=0
export AIHOT_ENABLE_SCHEDULE=0

DATE="${1:-}"
ARGS=(run)
if [[ -n "$DATE" ]]; then ARGS+=(--date "$DATE"); fi
if [[ -n "${AIHOT_GROUPS_FILE:-}" ]]; then ARGS+=(--groups-file "$AIHOT_GROUPS_FILE"); else ARGS+=(--skip-aihot); fi
if [[ -f data/feeds/${DATE:-2026-11-22}-builder.json ]]; then
  ARGS+=(--builder-feed "data/feeds/${DATE:-2026-11-22}-builder.json")
fi
if [[ -f data/feeds/${DATE:-2026-11-22}-deals.json ]]; then
  ARGS+=(--deals-feed "data/feeds/${DATE:-2026-11-22}-deals.json")
fi

mkdir -p "${AIHOT_LOG_DIR:-$ROOT/logs}"
LOG="${AIHOT_LOG_DIR:-$ROOT/logs}/unified-dry-$(date +%Y%m%d-%H%M%S).log"
python3 -m tools.aihot_pipeline "${ARGS[@]}" | tee "$LOG"
echo "log: $LOG"
