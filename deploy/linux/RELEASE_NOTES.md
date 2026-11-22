# Parent dry-run 部署说明（release 包）

## install.sh 行为摘要

| 项 | release 模式（默认） | git 模式（`AIHOT_INSTALL_MODE=git`） |
|----|----------------------|--------------------------------------|
| git clone / remote | **否** | 是 |
| sudo | **否** | 否（脚本本身不强制） |
| 写 systemd | **否** | 否 |
| 安装期联网 | **否** | 需要（clone） |
| 激活定时 | **否** | 否 |
| 导入真实凭据 | **否** | 否 |
| 默认 dry-run 门控 | 强制写入 env | 强制写入 env |

推荐：`AIHOT_HOME=~/aihot-daily-home bash deploy/linux/install.sh`

## 无副作用检查

`deploy/linux/check-no-side-effects.sh` 会强制：

- `AIHOT_ALLOW_LIVE_FETCH=0`（不 CDP 抓取）
- `AIHOT_FEISHU_ENABLED=0` / dry-run notify
- `AIHOT_ALLOW_GIT_PUSH=0`
- `AIHOT_ENABLE_SCHEDULE=0`

并写出 `logs/no-side-effects-*.log`。
