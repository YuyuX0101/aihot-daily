#!/usr/bin/env bash
# 对应惠普 run-if-missed.ps1：同一天只真正执行一次；12:00 前直接跳过。
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOW_HMS="$(date +%H:%M:%S)"
if [[ "$NOW_HMS" < "12:00:00" ]]; then
  exit 0
fi
STAMP="$ROOT/logs/.last-run-date"
TODAY="$(date +%Y-%m-%d)"
mkdir -p "$ROOT/logs"
if [[ -f "$STAMP" ]] && [[ "$(tr -d ' \r\n' < "$STAMP")" == "$TODAY" ]]; then
  exit 0
fi
export DISPLAY="${DISPLAY:-:4}"
export GIT_ASKPASS="${GIT_ASKPASS:-/tmp/git-askpass-daily.sh}"
export GIT_TERMINAL_PROMPT=0
export AIHOT_REPO_DIR="${AIHOT_REPO_DIR:-$ROOT/../aihot-daily}"
export AIHOT_LOG_DIR="${AIHOT_LOG_DIR:-$ROOT/logs}"
export AIHOT_KIMI_WORK_DIR="${AIHOT_KIMI_WORK_DIR:-/home/box/agent-data/daily-radar/kimi-work}"
# 与惠普一致：uv run 若无 uv 则回退 python3（零第三方依赖脚本）
if command -v uv >/dev/null 2>&1; then
  RUNNER=(uv run)
else
  RUNNER=(python3)
fi
mkdir -p "$ROOT/logs"
set +e
(
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] scheduled run start"
  "${RUNNER[@]}" "$ROOT/aihot-daily-generator.py"
  rc=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] scheduled run end rc=$rc"
  exit $rc
) >>"$ROOT/logs/scheduled-run.log" 2>&1
rc=$?
set -e
if [[ $rc -eq 0 ]]; then
  printf '%s\n' "$TODAY" > "$STAMP"
fi
exit $rc
