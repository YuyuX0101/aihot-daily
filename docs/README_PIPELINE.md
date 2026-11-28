# AIHOT 管线说明

GitHub Pages 静态托管。云侧通过 JSON 文件导入扩展 Builder / 羊毛雷达。

## 目录

| 路径 | 作用 |
|------|------|
| `YYYY-MM-DD.html` | 历史真实日报（正文与 URL 勿改；构建仅统一导航与样式） |
| `e/YYYY-MM-DD.html` | 统一期次 |
| `builder/` `deals/` | 栏目入口 |
| `data/feeds/` | 已核验生产 feed 备份 |
| `data/inbox/` → `editions/` | 摄取与合并 |
| `tests/examples/` | **仅测试**的 demo（`demo:true`） |
| `tools/aihot_pipeline/` | ingest / build / summary / notify |

## 站点封面

日常发布固定沿用现有封面，不再逐期生成或替换，也不在仓库中保存逐期 PNG 母图。只有明确要求整体更换站点封面时，才更新共享封面资源并运行 `python -m tools.aihot_pipeline build`。日报、Builder、羊毛与期次内页分别使用 `assets/covers/page-*.webp` 固定栏目配图，历史日报共用日报栏目图。

## Builder 文案与命名约定

GrokBot 每期必须为作品单独编辑名称和简介，不机械照抄速报标题：

- `title` 优先使用 `作品名：核心体验或用途`，作品名保留原始大小写，简短、可辨认，不堆砌营销词。
- `summary` 用一至两句话补充具体功能、使用场景或适合人群，建议 40–90 个汉字，至少说清“做什么、怎么用、面向谁”中的两项。不得只改写或重复标题，不以 `【速报转载 · 未独立核验 · 未实测】` 等标签开头。
- 作者声明、核验边界分别写入 `author_claim`、`verified_evidence`，不得混入作品简介。
- 首页和期次页会把中文冒号前的作品名作为卡片标题；没有分隔符时完整展示标题，因此不要连续使用多个冒号制造长标题。

示例：`文隐 TextVeil：在浏览器本地为文档脱敏`；简介可写 `支持常见文档格式，适合在交给 AI 前处理敏感内容。`

## 验收要点

- 生产页不得出现 example.com / 虚构优惠
- 标签只用「页面可达 / 作者声明 / 未实测 …」，禁止笼统 `verified`
- 时间显示北京时间
- deals=0 必须有诚实空状态文案
- 通知仅 dry-run

```bash
bash scripts/demo_pipeline.sh
python3 -m unittest discover -s tests -v
```
