# 生成器迁移接线说明（代码完成 ≠ 切流完成）

## 四态状态（请勿混淆）

| 状态 | 含义 | 本 PR |
|------|------|------|
| **代码完成** | 仓库内有可移植 runner、门控、部署包、离线测试 | ✅ |
| **离线测试** | unittest / dry-run / mock 防重发在 CI 或本机无副作用跑通 | ✅ |
| **云端真实验收** | parent 持久 Linux 上安装、Chrome/CDP、git、飞书配置实测 | ❌ 未做（需 parent） |
| **切流** | 停 HP 或单点切换、真实定时、真实推送与通知 | ❌ 禁止本阶段执行 |

## 库存脚本位置

- `vendor/box-inventory/`：box 脱敏拷贝（≈2026-11-18），**不声称等于当前 HP**
- 可移植逻辑：`tools/aihot_pipeline/{aihot_logic,aihot_fetch,unified_runner,feishu_gate,publish_gate}.py`
- 旧生成器内建的 Top5 飞书与 `git push main` **不会**被 unified runner 调用

## 依赖与缺口

| 依赖 | 离线 | 云端验收 |
|------|------|----------|
| Python 3.10+ stdlib | 足够 | 需要 |
| Chrome + DISPLAY + CDP | 不需要（`AIHOT_GROUPS_FILE` / mock） | 可能需要；`python3 -m tools.aihot_pipeline deps` 仅探针，`live_ready=false` |
| `feishu-webhook.json` | 不需要 | 切流前由 parent 放到 secrets 目录 |
| git push 凭证 | 不需要 | 切流前配置；默认 `AIHOT_ALLOW_GIT_PUSH=0` |

## Parent 部署（持久 Linux）

```bash
# 1) 安装运行目录（不启用 timer）
sudo AIHOT_HOME=/opt/aihot-daily bash deploy/linux/install.sh

# 2) 无副作用验收
bash /opt/aihot-daily/repo/deploy/linux/check-no-side-effects.sh

# 3) 手动 dry-run
bash /opt/aihot-daily/repo/deploy/linux/run-unified-dry.sh 2026-11-22
```

systemd 示例在 `deploy/linux/systemd/*.example`——**默认不要 enable**。与 HP `Kimi-AIHOT-Daily` 12:00 冲突前勿双开。

## 失败恢复

1. 构建/校验失败 → `notify` 跳过（`run_failed_no_notify` / `publish_failed_no_notify`）
2. 锁文件：`AIHOT_LOCK_DIR/unified.lock`（`flock`）
3. 补跑：`scripts/run-if-missed.sh` 在 12:00 后且 stamp 未写当日才执行；`AIHOT_ENABLE_SCHEDULE!=1` 时直接安全退出
4. 回滚：保持 HP 任务；云端保持 `AIHOT_DRY_RUN=1` 且不 enable timer

## 仍需确认

1. HP 任务今日是否仍 Ready / 是否已推 11-21 之后日报  
2. 与「日更雷达」Bot 切流协调，防双端 push/飞书  
3. parent 机 Chrome/CDP 与 headed 显示是否可用；否则继续文件导入 `AIHOT_GROUPS_FILE`
