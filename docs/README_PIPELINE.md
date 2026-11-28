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

## 每日封面

Grok bot 可为每期生成一张无文字横图，网页版本保存为 `assets/covers/YYYY-MM-DD.webp`（日期为北京时间业务日，建议 2048×896、质量 92）；无损 PNG 可作为母图保留。首页会按当前刊期自动读取 WebP；指定日期预览使用同一规则，文件不存在时回退到内置封面。生成图片后运行 `python -m tools.aihot_pipeline build`，无需修改 HTML 或 JavaScript。

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
