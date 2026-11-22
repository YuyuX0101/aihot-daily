#!/usr/bin/env bash
# Parent-host acceptance: zero network side effects for notify/push/schedule.
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== deps probe (no CDP scrape) =="
python3 -m tools.aihot_pipeline deps

echo "== unit + e2e offline =="
python3 -m unittest discover -s tests -v

echo "== unified dry-run with committed feeds (no legacy html write) =="
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
print("OK: checks finished without enabling schedule or live send.")
PY
