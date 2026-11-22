#!/usr/bin/env bash
# Shadow/demo pipeline — never sends Feishu, never touches production secrets.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p data/inbox
cp -f fixtures/mock/2026-11-21-builder.json \
      fixtures/mock/2026-11-21-deals.json \
      fixtures/mock/2026-11-21-daily.json \
      data/inbox/

python3 -m tools.aihot_pipeline ingest
python3 -m tools.aihot_pipeline build
python3 -m tools.aihot_pipeline summary 2026-11-21
python3 -m tools.aihot_pipeline notify 2026-11-21
echo "Demo pipeline finished (notify dry-run / unpublished gate)."
