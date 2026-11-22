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
  echo "== deps probe (no network; CDP not implemented) =="
  python3 -m tools.aihot_pipeline deps

  echo "== unit + e2e offline =="
  python3 -m unittest discover -s tests -v

  echo "== groups-file contract (unittest covers full smoke; do not mutate editions here) =="
  python3 - <<'PY'
import json
from pathlib import Path
from tools.aihot_pipeline.aihot_logic import filter_target_items
from datetime import date
g = json.loads(Path("tests/fixtures/aihot_groups_2026-11-22.json").read_text())["groups"]
items = filter_target_items(g, date(2026, 11, 22), today=date(2026, 11, 22))
assert len(items) == 2, items
assert Path("tests/fixtures/aihot_groups_2026-11-22.json").stat().st_size > 100
print(f"groups-file fixture OK: {len(items)} items above threshold for 2026-11-22")
PY

  echo "== restore committed official daily feed (offline JSON, no network) =="
  if [[ -f data/feeds/2026-11-22-daily-from-api.json ]]; then
    python3 - <<'PY'
import json
from pathlib import Path
from tools.aihot_pipeline.ingest import apply_feed
from tools.aihot_pipeline.build import build_site
from tools.aihot_pipeline.validate import validate_feed
feed = validate_feed(json.loads(Path("data/feeds/2026-11-22-daily-from-api.json").read_text()), allow_demo=False)
print(apply_feed(feed))
print(build_site())
PY
  fi

  echo "== unified dry-run with committed feeds (skip live aihot network) =="
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
  "AIHOT_HTTP_FETCH",
]
for k in keys:
    print(f"{k}={os.environ.get(k, '<unset>')}")
print("OK: offline checks finished without schedule/live send/push/CDP.")
print("For read-only live HTTP: bash deploy/linux/check-http-readonly.sh")
PY
} 2>&1 | tee "$LOG"

echo "log written: $LOG"
