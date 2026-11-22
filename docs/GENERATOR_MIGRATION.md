# 生成器迁移接线说明（代码完成 ≠ 切流完成）

## 四态状态（请勿混淆）

| 状态 | 含义 | 本 PR |
|------|------|------|
| **代码完成** | 可移植 runner、公开 HTTP 日报摄取、门控、部署包、离线测试 | ✅ |
| **离线测试** | unittest / dry-run / mock 防重发无副作用跑通 | ✅ |
| **只读 live HTTP** | `GET /api/v1/dailies` 真抓取证据（无 push/飞书） | ✅ 本机已跑通；parent 请重跑 `check-http-readonly.sh` |
| **云端真实验收** | parent 持久 Linux 解包安装 + 上述检查 | ⏳ parent 执行中 |
| **切流** | 停 HP、真实定时、真实推送与通知 | ❌ 禁止本阶段执行 |

## AIHOT 日报摄取（真实路径）

1. **推荐（公开 HTTP，无浏览器）**  
   `python3 -m tools.aihot_pipeline run --http-aihot`  
   → `https://aihot.news/api/v1/dailies/{date}`（文档：`/llms.txt`、`/agent?tab=api`）  
   标准库 `urllib`；匿名只读；不访问未公开凭据端点。

2. **Fallback（parent 外部上游）**  
   `--groups-file`：HP DOM 形状的 groups JSON。若上游只能有头浏览器读取首页，parent 用 box-desktop computerUse 抓取 `https://aihot.news/`，本仓库只消费文件。

3. **明确未实现**  
   CDP / 接管 Chrome 适配器已移除“假可用”入口；`cdp_ready=false` 恒成立。

### 日期语义

| 概念 | 值（以 2026-11-22 北京时间上午为例） |
|------|------|
| `beijing_today` | 2026-11-22 |
| HP 旧逻辑目标日 | **昨天** 2026-11-21（首页 score≥75） |
| 官方 API `dailies/latest.date` | **2026-11-22**（约 08:00 北京时间出刊） |
| 统一期次应使用 | 官方日报自己的 `date`，并在 meta 写明 `official_page` |
| 禁止 | 把本地旧 `2026-11-20.html` 等历史页冒充「当日日报」 |

## 库存脚本位置

- `vendor/box-inventory/`：box 脱敏拷贝（≈2026-11-18），**不声称等于当前 HP**；仅作旧 CDP 逻辑对照
- 可移植：`tools/aihot_pipeline/{aihot_http,aihot_logic,aihot_fetch,unified_runner,...}.py`
- 旧生成器 Top5 飞书与 `git push main` **不会**被 unified runner 调用

## 依赖

| 依赖 | 离线 | HTTP live 只读 | 切流 |
|------|------|----------------|------|
| Python 3.10+ stdlib | 足够 | 足够 | 足够 |
| 出网访问 `aihot.news` | 不需要 | **需要** | 需要 |
| Chrome + DISPLAY + CDP | 不需要 | **不需要** | 不需要（本方案） |
| groups-file | 可选 fallback | 可选 | 可选 |
| 飞书 / git push | 关闭 | 关闭 | 切流前再开 |

## Parent 部署（持久 Linux，解包优先）

```bash
tar -xzf aihot-release.tar.gz -C "$HOME/aihot-release"
cd "$HOME/aihot-release/aihot-release"
AIHOT_HOME="$HOME/aihot-daily-home" bash deploy/linux/install.sh
bash deploy/linux/check-no-side-effects.sh
bash deploy/linux/check-http-readonly.sh   # 只读 live HTTP；不 push/不发飞书
```

systemd 示例默认不要 enable。与 HP `Kimi-AIHOT-Daily` 12:00 冲突前勿双开。

## 仍需确认（切流前）

1. HP 任务是否仍 Ready；与「日更雷达」防双端 push/飞书  
2. parent 重跑 HTTP 只读验收并核对 `report.date` 与统一期次一致  
3. 切流时单点切换，本阶段保持 `AIHOT_DRY_RUN=1`、`AIHOT_ENABLE_SCHEDULE=0`、`AIHOT_FEISHU_ENABLED=0`
