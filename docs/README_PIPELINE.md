# AIHOT 管线说明

本仓库以 **GitHub Pages 静态托管** 为主。HP 上的 Windows 生成器未包含在仓库中；云侧通过 **JSON 文件导入** 扩展 Builder / 羊毛雷达，并生成统一期次页。

## 目录

| 路径 | 作用 |
|------|------|
| `YYYY-MM-DD.html` | 历史日报（URL 保持不变） |
| `e/YYYY-MM-DD.html` | 统一期次（daily + builder + deals） |
| `builder/` `deals/` | 栏目入口 |
| `data/inbox/` | 投放 JSON |
| `data/editions/` | 合并后的期次数据 |
| `tools/aihot_pipeline/` | 摄取 / 构建 / 摘要 dry-run |
| `docs/JSON_PROTOCOL.md` | 协议 |
| `docs/MIGRATION_CHECKLIST.md` | 迁移与回滚 |

## 快速体验

```bash
bash scripts/demo_pipeline.sh
python3 -m unittest discover -s tests -v
```

## 通知策略

- 默认 **dry-run**，且要求「网站已发布」标志，否则跳过发送。
- `--mock` 仅用于本地防重发测试，不接触网络。
- 仓库内 **不读取、不存储** 飞书 webhook secret；正式发送由父 Bot 注入 SendFn。
