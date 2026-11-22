#!/usr/bin/env bash
# Build aihot-release.tar.gz from the current working tree (no .git / secrets).
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-/opt/cursor/artifacts}"
STORE_DIR="${2:-/cursor/stores/self/releases}"
mkdir -p "$OUT_DIR" "$STORE_DIR" /tmp/aihot-release-stage

STAGE="/tmp/aihot-release-stage/aihot-release"
rm -rf "$STAGE"
mkdir -p "$STAGE"

# Ensure home snapshot exists
python3 -m tools.aihot_pipeline build >/tmp/aihot-build-for-release.json

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.git' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '**/.env' \
    --exclude '**/feishu-webhook.json' \
    --exclude '**/*webhook*.json' \
    --exclude '**/*.secret' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude 'logs/' \
    --exclude 'data/state/notify_state.json' \
    --exclude 'data/inbox/*.json' \
    --exclude 'data/archive/*.json' \
    --exclude '.cursor' \
    --exclude 'node_modules' \
    "$ROOT/" "$STAGE/"
else
  tar -C "$ROOT" \
    --exclude='.git' --exclude='.env' --exclude='.env.*' \
    --exclude='__pycache__' --exclude='.pytest_cache' --exclude='logs' \
    --exclude='.cursor' --exclude='node_modules' \
    --exclude='data/state/notify_state.json' \
    -cf - . | tar -C "$STAGE" -xf -
  find "$STAGE" -type f \( -name '.env' -o -name 'feishu-webhook.json' -o -name '*.secret' \) -delete
  find "$STAGE/data/inbox" -type f -name '*.json' -delete 2>/dev/null || true
  find "$STAGE/data/archive" -type f -name '*.json' -delete 2>/dev/null || true
fi

# remove any accidental browser profile dirs
find "$STAGE" -type d -name 'chrome-runtime-profile' -prune -exec rm -rf {} + 2>/dev/null || true

python3 - "$STAGE" "$ROOT" <<'PY'
import hashlib, json, os, subprocess
from datetime import datetime
from pathlib import Path
stage = Path(os.sys.argv[1])
root = Path(os.sys.argv[2])
files = []
for p in sorted(stage.rglob("*")):
    if p.is_file():
        rel = p.relative_to(stage).as_posix()
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": h, "bytes": p.stat().st_size})
try:
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
except Exception:
    commit, branch = "unknown", "unknown"
manifest = {
    "name": "aihot-release",
    "created_at_beijing": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    "git_branch": branch,
    "git_commit": commit,
    "excludes": [".git", ".env", "feishu-webhook.json", "browser profiles", "__pycache__", "logs"],
    "install": {
        "preferred": "AIHOT_HOME=~/aihot-daily-home bash deploy/linux/install.sh",
        "requires_sudo": False,
        "requires_git_clone": False,
        "writes_systemd": False,
        "network_for_install": False,
        "default_gates": {
            "AIHOT_DRY_RUN": "1",
            "AIHOT_ENABLE_SCHEDULE": "0",
            "AIHOT_FEISHU_ENABLED": "0",
            "AIHOT_ALLOW_GIT_PUSH": "0",
            "AIHOT_ALLOW_LIVE_FETCH": "0",
        },
    },
    "live_ready": False,  # pack-time default; parent should run deps --probe-http
    "live_ready_reason": (
        "Preferred live path is public HTTP GET https://aihot.news/api/v1/dailies "
        "(--http-aihot). CDP browser adapter is NOT implemented. "
        "Pack-time live_ready stays false until parent runs "
        "`python3 -m tools.aihot_pipeline deps --probe-http` / check-http-readonly.sh. "
        "Fallback: --groups-file from parent external capture."
    ),
    "cdp_adapter_implemented": False,
    "file_count": len(files),
    "files": files,
}
(stage / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(stage / "RELEASE_README.md").write_text(
"""# AIHOT release snapshot

## 解包安装（推荐，无需 git clone / 无需 sudo）

```bash
mkdir -p \"$HOME/aihot-release\" && tar -xzf aihot-release.tar.gz -C \"$HOME/aihot-release\"
cd \"$HOME/aihot-release/aihot-release\"
AIHOT_HOME=\"$HOME/aihot-daily-home\" bash deploy/linux/install.sh
AIHOT_HOME=\"$HOME/aihot-daily-home\" bash \"$HOME/aihot-daily-home/run-check.sh\"
```

- 默认不联网安装、不写 systemd、不启用定时、不导入凭据
- 检查脚本强制 dry-run，不真实抓取 / push / 发飞书
- 可选 `AIHOT_COPY_RELEASE=1` 将树复制到 `$AIHOT_HOME/app`
- 仅开发者需要时才设 `AIHOT_INSTALL_MODE=git`（会 clone）

## live_ready=false

见 RELEASE_MANIFEST.json 的 live_ready_reason。Parent 若要真实 CDP，需自备 headed Chrome/DISPLAY 并另开验收；本包 dry-run 不依赖。
""",
    encoding="utf-8",
)
print("manifest files", len(files))
PY

TAR="$OUT_DIR/aihot-release.tar.gz"
rm -f "$TAR"
tar -C /tmp/aihot-release-stage -czf "$TAR" aihot-release
SHA=$(sha256sum "$TAR" | awk '{print $1}')
echo "$SHA  aihot-release.tar.gz" | tee "$OUT_DIR/aihot-release.tar.gz.sha256"
cp -f "$TAR" "$STORE_DIR/aihot-release.tar.gz"
cp -f "$OUT_DIR/aihot-release.tar.gz.sha256" "$STORE_DIR/aihot-release.tar.gz.sha256"
cp -f "$STAGE/RELEASE_MANIFEST.json" "$OUT_DIR/aihot-release.manifest.json"
cp -f "$STAGE/RELEASE_MANIFEST.json" "$STORE_DIR/aihot-release.manifest.json"

python3 - <<PY
import json
from pathlib import Path
m = json.loads(Path("$STAGE/RELEASE_MANIFEST.json").read_text())
print(json.dumps({
  "tar": "$TAR",
  "sha256": "$SHA",
  "store_tar": "$STORE_DIR/aihot-release.tar.gz",
  "file_count": m["file_count"],
  "git_commit": m["git_commit"],
}, ensure_ascii=False, indent=2))
PY
