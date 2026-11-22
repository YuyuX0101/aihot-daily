#!/usr/bin/env bash
# Read-only live HTTP acceptance against aihot.news public API.
# NEVER enables push / Feishu send / schedule / CDP browser.
set -euo pipefail
export TZ=Asia/Shanghai
export AIHOT_DRY_RUN=1
export AIHOT_ENABLE_SCHEDULE=0
export AIHOT_ALLOW_GIT_PUSH=0
export AIHOT_ALLOW_PUSH_MAIN=0
export AIHOT_FEISHU_ENABLED=0
# HTTP read allowed for this script only; still dry-run for publish/notify
export AIHOT_HTTP_FETCH=1

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG_DIR="${AIHOT_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR" data/sources data/feeds
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/http-readonly-$STAMP.log"
EVIDENCE="data/sources/aihot-http-live-$STAMP.json"
FEED="data/feeds/aihot-http-daily-live.json"

{
  echo "== deps --probe-http =="
  python3 -m tools.aihot_pipeline deps --probe-http

  echo "== fetch-aihot (read-only evidence) =="
  python3 -m tools.aihot_pipeline fetch-aihot \
    --save-evidence "$EVIDENCE" \
    --write-feed "$FEED"

  DATE="$(python3 -c "import json; print(json.load(open('$FEED'))['edition_date'])")"
  echo "== resolved official daily date: $DATE =="

  echo "== unified dry-run with HTTP daily + committed builder/deals =="
  BF="data/feeds/${DATE}-builder.json"
  DF="data/feeds/${DATE}-deals.json"
  ARGS=(run --http-aihot --date "$DATE")
  if [[ -f "$BF" ]]; then ARGS+=(--builder-feed "$BF"); fi
  if [[ -f "$DF" ]]; then ARGS+=(--deals-feed "$DF"); fi
  python3 -m tools.aihot_pipeline "${ARGS[@]}"

  echo "== notify remains dry-run / unpublished skip =="
  python3 -m tools.aihot_pipeline notify "$DATE"

  echo "OK: HTTP readonly path finished; no push/send/schedule."
  echo "evidence=$EVIDENCE feed=$FEED"
} 2>&1 | tee "$LOG"

echo "log written: $LOG"
