# AIHOT 生成器脱敏迁移资料包

本包只提供已存在于共享 box 上的项目脚本拷贝，供 Cloud Agent 做代码调查与把生成器接到已完成的静态整合（cloud PR1）。

## 本包约束（请遵守）

- 打包时间：2026-11-22（Asia/Shanghai，box 本地时区）
- 本包是 box 存货拷贝，**不声称与惠普 LAPTOP-C6C240GO 当前文件一致**。惠普在这些拷贝落地之后仍可能改过脚本（既有记录里，2026-11-10 左右曾在惠普上修过生成器；远端仓库此后仍按每天中午推送日报，直到 2026-11-21 12:00:51 Asia/Shanghai 的 `update: 2026-11-20 daily`）。
- 文件 mtime 几乎都是 2026-11-18 23:03（Asia/Shanghai），与当时 workspace 批量落地时间一致，**不能当作惠普上的编写或最后修改时间**。
- 打包前已扫描硬编码 token / webhook URL / secret / 私钥块；本次**无需替换**（0 处红action）。飞书凭据在同目录 `feishu-webhook.json` 的 `url` 与 `secret` 字段，**本包故意不收录**该文件，也不收录 `.env`、私钥、askpass、token。
- 使用本包时不要运行生成器、不要 git push、不要发送飞书通知、不要把示例路径里的凭据文件读进报告。
- 本包不含 `YuyuX0101/aihot-daily` 仓库检出（box 上的 `/workspace/daily-radar/aihot-daily` 已过期，只到 2026-11-08 日报）。站点源请以 GitHub 远端 `main` 为准。

## 仓库与站点（此前只读盘点，供对照）

- 日报 Pages 仓库：https://github.com/YuyuX0101/aihot-daily
- 公网站点：https://yuyux0101.github.io/aihot-daily/
- 上游数据源（非用户托管站）：https://aihot.virxact.com/
- 惠普项目根（拷贝中的路径，未在本轮实连核验）：`E:\workspace\aihot\`
- 惠普 Pages 仓检出路径（拷贝中的路径）：`E:\workspace\aihot\aihot-daily-repo`
- 惠普计划任务名：`Kimi-AIHOT-Daily`（每天 12:00 Asia/Shanghai + 登录后 5 分钟补跑）
- 惠普飞书模块路径（拷贝中的路径）：`C:\Users\92926\.kimi-work\feishu_notify.py`
- 惠普 git remote（拷贝中的值）：`git@github.com:YuyuX0101/aihot-daily.git`

## 文件清单

### `aihot-daily-generator.py`

- 作用：Box 上的 Linux/云电脑适配版生成器。注释写明源自惠普 aihot-daily-generator-win.py，只做环境路径适配。
- 复制自：`/workspace/daily-radar/aihot/aihot-daily-generator.py`
- 源文件在 box 上的 mtime：2026-11-18 23:03:08（Asia/Shanghai）
- 大小：37957 字节
- SHA-256：`af358c75b707dc9c3571cc151e9274ed04e031c94b5a6479e955dfb797b48ec0`
- 硬编码密钥替换：无（扫描 0 处）
- 可能过期：是。这是 2026-11-18 前后留在 box 上的拷贝，不能当作惠普当前版本。

### `aihot-daily-generator-win.py`

- 作用：惠普 Windows 生成器的 box 存货拷贝，供对照路径与计划任务入口，不代表惠普当前文件。
- 复制自：`/workspace/daily-radar/_inventory/aihot-daily-generator-win.py`
- 源文件在 box 上的 mtime：2026-11-18 23:03:09（Asia/Shanghai）
- 大小：37674 字节
- SHA-256：`32dda29c67b6473702f1b155ac87d40b1a9e52bc0208db11fa0a421dc5609a7f`
- 硬编码密钥替换：无（扫描 0 处）
- 可能过期：是。这是 2026-11-18 前后留在 box 上的拷贝，不能当作惠普当前版本。

### `scripts/run-if-missed.sh`

- 作用：Box 侧与惠普 run-if-missed.ps1 对应的包装脚本：同一天只跑一次，12:00 前跳过。
- 复制自：`/workspace/daily-radar/aihot/scripts/run-if-missed.sh`
- 源文件在 box 上的 mtime：2026-11-18 23:03:07（Asia/Shanghai）
- 大小：1318 字节
- SHA-256：`a051cc00e0acc433a793b8f969488a4b6d95db7a8636673c16b2ad101541cc43`
- 硬编码密钥替换：无（扫描 0 处）
- 可能过期：是。这是 2026-11-18 前后留在 box 上的拷贝，不能当作惠普当前版本。

### `scripts/run-if-missed.ps1`

- 作用：惠普计划任务 Kimi-AIHOT-Daily 的入口包装脚本拷贝。
- 复制自：`/workspace/daily-radar/_inventory/run-if-missed.ps1`
- 内容相同的另一份源路径：/workspace/daily-radar/aihot/scripts/run-if-missed.ps1
- 源文件在 box 上的 mtime：2026-11-18 23:03:11（Asia/Shanghai）
- 大小：922 字节
- SHA-256：`6fa04635ca2633786fb0d3299789709f4c4d7c672b9070511975ea072bc78c9c`
- 硬编码密钥替换：无（扫描 0 处）
- 可能过期：是。这是 2026-11-18 前后留在 box 上的拷贝，不能当作惠普当前版本。

### `feishu_notify.py`

- 作用：Kimi Work 共享飞书通知模块实现。Linux 生成器默认从 AIHOT_KIMI_WORK_DIR（缺省 /home/box/agent-data/daily-radar/kimi-work）导入。本包只含源码，不含 feishu-webhook.json。
- 复制自：`/home/box/sand-data/daily-radar/kimi-work/feishu_notify.py`
- 源文件在 box 上的 mtime：2026-11-18 23:03:10（Asia/Shanghai）
- 大小：4021 字节
- SHA-256：`49758e622697f82765de184d2bd390c52d2736a1ee154c21fe4ecfe93d25aa05`
- 硬编码密钥替换：无（扫描 0 处）
- 可能过期：是。这是 2026-11-18 前后留在 box 上的拷贝，不能当作惠普当前版本。

## 故意未收入本包的文件

- 任何 `feishu-webhook.json`（已知位置包括 `/home/box/agent-data/daily-radar/kimi-work/feishu-webhook.json` 及其 `secrets/`、`yinyu-handoff/notify/` 副本）。字段名仅为 `name`、`description`、`url`、`secret`，值为凭据，不要读取。
- `.env`、私钥、`GIT_ASKPASS` 脚本（Linux 包装脚本提到 `/tmp/git-askpass-daily.sh`，与 OSR 同套，本包不收录）。
- `/workspace/yinyu-handoff/notify/feishu_notify.py`：与本包中的 `feishu_notify.py` **内容不同**，且不是 Linux 生成器默认导入路径，为避免混用未打包。
- 生成器日志、Chrome/Edge 运行时配置、以及 `/workspace/daily-radar/aihot-daily` 仓库检出。

## 下一步必须确认（本包不处理，且不要联系其他 Bot）

1. **惠普任务状态**：`Kimi-AIHOT-Daily` 是否仍为 Ready。只读盘点时，远端最近一次日报推送是 2026-11-21 12:00:51（Asia/Shanghai）；今天（2026-11-22）中午是否仍会跑，本包无法证明。在云上生成器接好并经验证前，不要停惠普任务，避免漏更；也不要让 box 与惠普双端同时执行，避免重复 push / 重复飞书。
2. **与「日更雷达」协调**：AIHOT / NovelRadar / OSR 的迁移此前已交给专职 Bot「日更雷达」（id `fc1b875d-c5a7-4f0b-b1d8-99cabf551ae2`）。当时约定云上跑通后再停惠普对应任务。本包由当前迁移线提供给 Cloud Agent，**不要在未对齐的情况下另开一条切流**。协调由 parent / 用户进行，不要由本资料包的使用方去联络其他 Bot。
