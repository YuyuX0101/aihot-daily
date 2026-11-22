# AIHOT 统一摄取协议（v1）

面向「AI HOT 日报 / Builder 一手作品速报 / AI 羊毛雷达」的文件导入协议。  
Bot 或人工将 JSON 放入 `data/inbox/`，由本地管线幂等摄取并构建静态页。

## 投放方式

```bash
cp data/feeds/<file>.json data/inbox/
python3 -m tools.aihot_pipeline ingest
python3 -m tools.aihot_pipeline build
python3 -m tools.aihot_pipeline notify --dry-run   # 默认即 dry-run
```

成功摄取的文件移至 `data/archive/`；合并结果写入 `data/editions/YYYY-MM-DD.json`。

## Demo / 示例隔离（硬规则）

- 示例仅允许放在 `tests/examples/`，且必须 `"demo": true`
- 生产 `ingest` **拒绝** `demo=true`、example.com 主机、以及笼统 `verified/tested/played/audited` 标签
- 对外期次页禁止混入虚构优惠/作品；若确需本地演示页，必须全局醒目「示例预览」横幅（本仓库生产输出不生成该页）

## 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `schema_version` | 是 | `"1.0"` |
| `edition_date` | 是 | `YYYY-MM-DD`（业务日，北京时间） |
| `channel` | 是 | `daily` \| `builder` \| `deals` |
| `source` | 是 | 如 `bot-x-web` |
| `generated_at` | 是 | ISO-8601 |
| `items` | 是 | 可为空数组 |
| `channel_meta` | 否 | 空栏目说明（如 deals=0 原因），**不用于伪造条目** |
| `demo` | 否 | 仅 tests/examples |

## 条目字段

公共：`id`（稳定）、`title`、`summary`、`source_url`、`playable_url`、`repo_url`、`author`、`published_at`、`verified_at`、`notes`、`score`

Builder 语义字段：

| 字段 | 说明 |
|------|------|
| `author_claim` | 作者声明（未当作已审计事实） |
| `verified_evidence` | 核验正文证据（页可打开、仓库存在等） |
| `verification_tags` | 仅允许：`page_reachable` / `author_claim` / `untested` / `repo_reachable` / `hearsay` / `no_playable` |

**禁止** `verified` 等笼统标签，以免被理解成「已实测」。

deals 专属：`deal.threshold` / `deadline` / `regions` / `restrictions`

## 空栏目约定

- `items: []` + `channel_meta.empty_message` 说明原因
- deals=0 示例文案：说明「未找到同时满足最近12h新鲜度+可核验」——**不等于全网无优惠**
- 当日无 AIHOT 日报：链接历史 `YYYY-MM-DD.html`，不插示例

## 时间展示

管线渲染一律转为 **Asia/Shanghai**，显示为 `YYYY-MM-DD HH:MM 北京时间`，不在页面裸露末尾 `Z`。

## 安全

HTML 转义；拒绝 `javascript:` / `data:`；拒绝 script/事件注入特征；字段长度与条目上限。
