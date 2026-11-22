#!/usr/bin/env bash
# Rebuild the committed 2026-11-22 production preview from data/feeds/.
# Never sends Feishu. Demo fixtures under tests/examples/ are NOT copied to inbox.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p data/inbox
# Clear any leftover inbox files first
rm -f data/inbox/*.json
cp -f data/feeds/2026-11-22-builder.json \
      data/feeds/2026-11-22-deals.json \
      data/feeds/2026-11-22-daily.json \
      data/inbox/

python3 -m tools.aihot_pipeline ingest
python3 -m tools.aihot_pipeline build
python3 -m tools.aihot_pipeline summary 2026-11-22
python3 -m tools.aihot_pipeline notify 2026-11-22
echo "Pipeline finished (notify dry-run / unpublished gate). Demo fixtures were not used."
