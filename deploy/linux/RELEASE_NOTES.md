# Parent dry-run 部署说明（release 包）

## AIHOT 真实摄取路径（本轮）

| 路径 | 说明 |
|------|------|
| **推荐 live** | `python3 -m tools.aihot_pipeline run --http-aihot` → 公开匿名 `GET https://aihot.news/api/v1/dailies/{date}`（标准库 urllib，无浏览器/CDP） |
| 文档 | https://aihot.news/llms.txt 、https://aihot.news/agent?tab=api |
| 只读验收 | `bash deploy/linux/check-http-readonly.sh` |
| 离线/fallback | `--groups-file`（parent 外部有头抓取首页 DOM 的 groups JSON） |
| **未实现** | CDP / 接管浏览器适配器（已删除“假可用”入口） |

日期语义：官方日报 `report.date` 为栏目来源日；HP 旧逻辑是北京时间「昨天」首页 score≥75。不得把本地旧 `YYYY-MM-DD.html`（如 11-20）冒充当日日报。

## install.sh 行为摘要

| 项 | release 模式（默认） | git 模式（`AIHOT_INSTALL_MODE=git`） |
|----|----------------------|--------------------------------------|
| git clone / remote | **否** | 是 |
| sudo | **否** | 否 |
| 写 systemd | **否** | 否 |
| 安装期联网 | **否** | 需要（clone） |
| 激活定时 / 凭据 | **否** | 否 |
| 默认 dry-run 门控 | 强制 | 强制 |

## live_ready

- 打包时 `live_ready=false`（避免未探测即宣称）
- parent 执行 `deps --probe-http` 或 `check-http-readonly.sh` 成功后，探针可报 `live_ready=true` **仅表示公开 HTTP API 可读**，不是 CDP、不是发布/飞书就绪
- `cdp_ready` 恒为 false
