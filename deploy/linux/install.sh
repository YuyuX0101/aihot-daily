#!/usr/bin/env bash
# Install AIHOT runner package onto a persistent Linux host (parent machine).
# Does NOT enable cron/systemd timers. Does NOT send Feishu. Does NOT push git.
set -euo pipefail
export TZ=Asia/Shanghai

PREFIX="${AIHOT_HOME:-/opt/aihot-daily}"
REPO_URL="${AIHOT_REPO_URL:-https://github.com/YuyuX0101/aihot-daily.git}"
BRANCH="${AIHOT_INSTALL_BRANCH:-cursor/integrate-builder-deals-9c12}"

echo "[install] prefix=$PREFIX branch=$BRANCH"
sudo mkdir -p "$PREFIX"/{logs,locks,secrets,inbox,feeds}
sudo chown -R "${SUDO_USER:-$USER}:${SUDO_USER:-$USER}" "$PREFIX" || true

if [[ ! -d "$PREFIX/repo/.git" ]]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$PREFIX/repo"
else
  git -C "$PREFIX/repo" fetch origin "$BRANCH"
  git -C "$PREFIX/repo" checkout "$BRANCH"
  git -C "$PREFIX/repo" pull --ff-only origin "$BRANCH" || true
fi

mkdir -p "$PREFIX/config"
if [[ ! -f "$PREFIX/config/aihot.env" ]]; then
  cp "$PREFIX/repo/config/aihot.example.env" "$PREFIX/config/aihot.env"
  sed -i "s|^AIHOT_HOME=.*|AIHOT_HOME=$PREFIX|" "$PREFIX/config/aihot.env"
  sed -i "s|^AIHOT_REPO_DIR=.*|AIHOT_REPO_DIR=$PREFIX/repo|" "$PREFIX/config/aihot.env"
  sed -i "s|^AIHOT_LOG_DIR=.*|AIHOT_LOG_DIR=$PREFIX/logs|" "$PREFIX/config/aihot.env"
  sed -i "s|^AIHOT_LOCK_DIR=.*|AIHOT_LOCK_DIR=$PREFIX/locks|" "$PREFIX/config/aihot.env"
  sed -i "s|^AIHOT_KIMI_WORK_DIR=.*|AIHOT_KIMI_WORK_DIR=$PREFIX/secrets|" "$PREFIX/config/aihot.env"
  echo "[install] wrote $PREFIX/config/aihot.env (edit before cutover)"
fi

echo "[install] DONE. Next: bash $PREFIX/repo/deploy/linux/check-no-side-effects.sh"
echo "[install] Timers NOT enabled. Keep AIHOT_ENABLE_SCHEDULE=0 until HP noon task is coordinated."
