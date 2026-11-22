#!/usr/bin/env bash
# Parent-host / unpacked-release acceptance: zero outbound side effects.
set -euo pipefail
export TZ=Asia/Shanghai

# Force safety regardless of ambient env
export AIHOT_DRY_RUN=1
export AIHOT_ENABLE_SCHEDULE=0
export AIHOT_ALLOW_LIVE_FETCH=0
export AIHOT_ALLOW_GIT_PUSH=0
export AIHOT_ALLOW_PUSH_MAIN=0
export AIHOT_FEISHU_ENABLED=0

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG_DIR="${AIHOT_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/no-side-effects-$STAMP.log"

{
  echo "== cwd=$ROOT =="
  echo "== deps probe (no CDP scrape, no network fetch of aihot) =="
  python3 -m tools.aihot_pipeline deps

  echo "== unit + e2e offline =="
  python3 -m unittest discover -s tests -v

  echo "== unified dry-run with committed feeds (skip live aihot) =="
  python3 -m tools.aihot_pipeline run --date 2026-11-22 \
    --skip-aihot \
    --builder-feed data/feeds/2026-11-22-builder.json \
    --deals-feed data/feeds/2026-11-22-deals.json

  echo "== notify dry-run (must skip unpublished) =="
  python3 -m tools.aihot_pipeline notify 2026-11-22

  echo "== env safety snapshot =="
  python3 - <<'PY'
import os
keys = [
  "AIHOT_DRY_RUN","AIHOT_ENABLE_SCHEDULE","AIHOT_ALLOW_LIVE_FETCH",
  "AIHOT_ALLOW_GIT_PUSH","AIHOT_ALLOW_PUSH_MAIN","AIHOT_FEISHU_ENABLED",
]
for k in keys:
    print(f"{k}={os.environ.get(k, '<unset>')}")
print("OK: checks finished without schedule/live send/push/scrape.")
PY
} 2>&1 | tee "$LOG"

echo "log written: $LOG"
