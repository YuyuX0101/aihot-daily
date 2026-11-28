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

日常发布固定沿用现有封面，不再逐期生成或替换，也不在仓库中保存逐期 PNG 母图。只有明确要求整体更换站点封面时，才更新共享封面资源并运行 `python -m tools.aihot_pipeline build`。

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
