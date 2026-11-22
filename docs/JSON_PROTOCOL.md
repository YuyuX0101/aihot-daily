# AIHOT 统一摄取协议（v1）

面向「AI HOT 日报 / Builder 一手作品速报 / AI 羊毛雷达」的文件导入协议。  
Bot 或人工将 JSON 放入 `data/inbox/`，由本地管线幂等摄取并构建静态页。无需新增付费 API 或常驻服务。

## 投放方式

1. 将符合本协议的 JSON 文件复制到 `data/inbox/`（文件名任意，建议 `YYYY-MM-DD-<channel>-<slug>.json`）。
2. 运行：

```bash
python3 -m tools.aihot_pipeline ingest
python3 -m tools.aihot_pipeline build
python3 -m tools.aihot_pipeline notify --dry-run
```

3. 成功摄取的文件移至 `data/archive/`；合并结果写入 `data/editions/YYYY-MM-DD.json`。

## 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `schema_version` | 是 | 固定 `"1.0"` |
| `edition_date` | 是 | `YYYY-MM-DD`，北京时间业务日 |
| `channel` | 是 | `daily` \| `builder` \| `deals` |
| `source` | 是 | 来源标识，如 `bot-x-web`、`file-import`、`hp-legacy` |
| `generated_at` | 是 | ISO-8601 生成时间 |
| `items` | 是 | 条目数组，可为空 |

## 条目公共字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | **稳定 ID**（跨重导入不变）。建议 `channel:hash(source_url)` 或上游主键 |
| `title` | 是 | 标题，纯文本，最长 200 字 |
| `summary` | 否 | 摘要，纯文本，最长 2000 字 |
| `source_url` | 否 | 原文 URL（`http`/`https` only） |
| `author` | 否 | 作者/账号 |
| `published_at` | 否 | 发布时间 ISO-8601 |
| `verified_at` | 否 | 核查时间 ISO-8601 |
| `verification_tags` | 否 | 字符串数组，如 `verified`、`hearsay`、`untested` |
| `notes` | 否 | 未实玩备注等说明，最长 500 字 |
| `score` | 否 | 可选排序分（整数） |

## deals 专属字段 `deal`

| 字段 | 必填 | 说明 |
|------|------|------|
| `threshold` | 否 | 优惠门槛，如「新用户免费 7 天」 |
| `deadline` | 否 | 截止日 `YYYY-MM-DD` 或 ISO-8601 |
| `regions` | 否 | 地区限制数组，如 `["CN","US"]` |
| `restrictions` | 否 | 其他限制说明 |

## 幂等与去重

- 主键：`(edition_date, channel, id)`
- 同日同频道同 `id` 再次导入时，以**较新的 `verified_at` / `generated_at`** 覆盖
- 无 `id` 或非法 `id` 的条目整条拒绝

## 安全约束

管线会：

- HTML 转义全部展示字段，禁止把未转义文本写入页面
- 拒绝 `javascript:`、`data:` 等危险 URL scheme
- 拒绝含 `<script` / 事件处理器特征的原始字段（硬拒绝，不尝试「清洗后放行」）
- 限制字段长度与条目数量（单文件 ≤ 500 条）

## 最小示例

见 `fixtures/mock/`。
