# HP → Grok Bot 云电脑迁移检查单（可回滚）

> 目标：把**生成与通知编排**迁到云电脑，**网站继续 GitHub Pages 静态托管**。  
> 本仓库变更**不切生产、不停 HP 任务、不实发飞书、不改 DNS**。正式切流由父 Bot / 负责人协调。

## 现状结论（调查时）

| 项 | 状态 |
|----|------|
| 远端 `main` | `7b395b7`（2026-11-20 日报） |
| GitHub Pages | `https://yuyux0101.github.io/aihot-daily/`，历史 `YYYY-MM-DD.html` |
| 上游数据源 | `https://aihot.virxact.com/`（仅数据，非托管） |
| 本仓库内容 | 静态 HTML + `days.json` + 路径绑定的 `generate_daily.py` |
| HP 生产脚本 | **不在仓库内**（`E:\workspace\aihot\` 等）；不可假定已提交 |
| 飞书凭据 | 仅在 HP 本机 `feishu-webhook.json`；**禁止读入/提交仓库** |
| box 旧稿 | 非本 VM；不可当源 |

## 未知项 / 风险

1. HP 上是否有未 push 的生成器改动或日志状态（未实连确认）。
2. 是否另有 Bot 的「日更雷达」迁移计划并行——**正式切流前必须协调**，防止双端 push / 双发飞书。
3. 云电脑是否具备稳定出站、git push 权限与北京时间调度；父 Bot 负责 routines，本仓库不改其调度。
4. 生产飞书机器人签名算法与 `send_feishu_text` 实现细节需父 Bot 提供脱敏脚本后再接线。
5. 历史日报摘要质量门禁逻辑在 HP 侧；本仓库仅提供统一频道摄取，不凭空还原完整生产爬虫。

## 推荐切流阶段（保持旧生产运行）

### 阶段 A — 并行影子（当前 PR）

- [x] JSON 摄取协议 + 幂等去重 + 注入防护
- [x] 静态站点新增 `builder/`、`deals/`、`e/YYYY-MM-DD.html`
- [x] 保留全部历史 `YYYY-MM-DD.html` URL
- [x] 飞书摘要默认 dry-run；mock 防重发测试
- [ ] 父 Bot 用脱敏脚本在云电脑跑影子生成（**不 push main / 不通知**）
- [ ] 对比影子输出与 HP 输出差异

### 阶段 B — 只读预发分支

- [ ] 云电脑 push 到预发分支或 fork，开启 Pages 预览（若可用）
- [ ] 人工验收统一期次页与摘要文案
- [ ] 确认通知仍 dry-run

### 阶段 C — 通知切换（需人工批准）

- [ ] 确认网站发布成功后再发飞书（`notify --published`）
- [ ] **先停一端**：要么暂停 HP 任务，要么云端不发——禁止双发
- [ ] 将 webhook 配置放在云电脑密钥文件（不进 git）
- [ ] 观察 ≥1 个业务日

### 阶段 D — 生成切换

- [ ] HP 任务改为 disabled（保留定义便于回滚）
- [ ] 云电脑成为唯一 ingest→build→push→notify 执行者
- [ ] 更新运维备注：根目录、日志路径、幂等脚本

## 回滚步骤（摘要）

1. **立即**：云电脑侧停止 push 与 notify（父 Bot 调度层）。
2. **恢复 HP**：重新启用 `Kimi-AIHOT-Daily` 任务（12:00 + 登录补跑）。
3. **仓库**：如预发分支已误合入，`git revert` 合并提交；历史日报文件通常无需回滚。
4. **飞书**：确认仅 HP 发送；清理云端 notify state，避免回切后再发重复摘要。
5. **验证**：检查 Pages 最新 `YYYY-MM-DD.html` 与群消息来源。

## 本仓库命令（脱敏）

```bash
# 投放 JSON
cp fixtures/mock/2026-11-21-*.json data/inbox/

python3 -m tools.aihot_pipeline ingest
python3 -m tools.aihot_pipeline build
python3 -m tools.aihot_pipeline summary 2026-11-21
python3 -m tools.aihot_pipeline notify 2026-11-21          # dry-run，且默认未发布则跳过发送
python3 -m tools.aihot_pipeline notify 2026-11-21 --mock --published --allow-unpublished
```

## 禁止事项（再次确认）

- 不切 DNS / 不停未批准的 HP 任务 / 不实发外部消息
- 不购买付费 API、不假设 grok CLI / Bot 私有工具可用
- 不向仓库提交 `feishu-webhook.json` 或任何 secret
- 不自动启用真实 cron；调度由父 Bot 管理
