#!/usr/bin/env bash
# Install / prepare AIHOT runner for parent persistent Linux.
#
# Modes:
#   1) Release unpack (preferred): run from an extracted aihot-release/ tree.
#      No git clone, no sudo, no systemd, no network required for install itself.
#   2) Optional git mode: only if AIHOT_INSTALL_MODE=git (NOT default).
#
# Does NOT enable timers, send Feishu, push git, or import secrets.
set -euo pipefail
export TZ=Asia/Shanghai

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer release layout: deploy/linux -> repo root
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PREFIX="${AIHOT_HOME:-$HOME/aihot-daily-home}"
MODE="${AIHOT_INSTALL_MODE:-release}"

echo "[install] mode=$MODE"
echo "[install] AIHOT_HOME=$PREFIX"
echo "[install] repo_root=$REPO_ROOT"

mkdir -p "$PREFIX"/{logs,locks,secrets,inbox,feeds,config}

if [[ "$MODE" == "git" ]]; then
  echo "[install] WARNING: git mode clones/fetches remote — only for developers."
  REPO_URL="${AIHOT_REPO_URL:-https://github.com/YuyuX0101/aihot-daily.git}"
  BRANCH="${AIHOT_INSTALL_BRANCH:-cursor/integrate-builder-deals-9c12}"
  TARGET_REPO="${PREFIX}/repo"
  if [[ ! -d "$TARGET_REPO/.git" ]]; then
    git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_REPO"
  else
    git -C "$TARGET_REPO" fetch origin "$BRANCH"
    git -C "$TARGET_REPO" checkout "$BRANCH"
    git -C "$TARGET_REPO" pull --ff-only origin "$BRANCH" || true
  fi
  REPO_ROOT="$TARGET_REPO"
else
  # release mode: use the unpacked tree in-place (or copy tree into AIHOT_HOME/app)
  if [[ "${AIHOT_COPY_RELEASE:-0}" == "1" ]]; then
    APP="$PREFIX/app"
    mkdir -p "$APP"
    # copy without clobbering secrets/logs outside app (rsync optional)
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete \
        --exclude '.git' --exclude '.env' --exclude '**/feishu-webhook.json' \
        --exclude 'logs/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
        "$REPO_ROOT/" "$APP/"
    else
      rm -rf "$APP"
      mkdir -p "$APP"
      tar -C "$REPO_ROOT" --exclude='.git' --exclude='.env' --exclude='logs' \
        --exclude='__pycache__' --exclude='.pytest_cache' -cf - . | tar -C "$APP" -xf -
    fi
    REPO_ROOT="$APP"
    echo "[install] copied release tree to $APP"
  else
    echo "[install] using unpacked release in-place at $REPO_ROOT"
    echo "[install] set AIHOT_COPY_RELEASE=1 to copy into \$AIHOT_HOME/app"
  fi
fi

ENV_OUT="$PREFIX/config/aihot.env"
if [[ ! -f "$ENV_OUT" ]]; then
  cp "$REPO_ROOT/config/aihot.example.env" "$ENV_OUT"
  # portable sed: rewrite key lines
  python3 - "$ENV_OUT" "$PREFIX" "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path
path, prefix, repo = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
repl = {
    "AIHOT_HOME": prefix,
    "AIHOT_REPO_DIR": repo,
    "AIHOT_LOG_DIR": f"{prefix}/logs",
    "AIHOT_LOCK_DIR": f"{prefix}/locks",
    "AIHOT_KIMI_WORK_DIR": f"{prefix}/secrets",
}
lines = []
for line in text.splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in repl:
            lines.append(f"{k}={repl[k]}")
            continue
    lines.append(line)
# force safety gates
forced = {
    "AIHOT_DRY_RUN": "1",
    "AIHOT_ENABLE_SCHEDULE": "0",
    "AIHOT_ALLOW_LIVE_FETCH": "0",
    "AIHOT_ALLOW_GIT_PUSH": "0",
    "AIHOT_ALLOW_PUSH_MAIN": "0",
    "AIHOT_FEISHU_ENABLED": "0",
}
out = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in forced:
            out.append(f"{k}={forced[k]}")
            seen.add(k)
            continue
    out.append(line)
for k, v in forced.items():
    if k not in seen:
        out.append(f"{k}={v}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(path)
PY
  echo "[install] wrote $ENV_OUT (dry-run gates forced ON)"
else
  echo "[install] keep existing $ENV_OUT"
fi

cat > "$PREFIX/run-check.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export TZ=Asia/Shanghai
set -a; source "$ENV_OUT"; set +a
cd "$REPO_ROOT"
mkdir -p "\$AIHOT_LOG_DIR"
LOG="\$AIHOT_LOG_DIR/check-\$(date +%Y%m%d-%H%M%S).log"
bash deploy/linux/check-no-side-effects.sh 2>&1 | tee "\$LOG"
echo "log=\$LOG"
EOF
chmod +x "$PREFIX/run-check.sh"

echo "[install] DONE"
echo "[install] No systemd units written. No sudo required in release mode."
echo "[install] Next: AIHOT_HOME=$PREFIX bash $PREFIX/run-check.sh"
echo "[install] Or:  cd $REPO_ROOT && bash deploy/linux/check-no-side-effects.sh"
