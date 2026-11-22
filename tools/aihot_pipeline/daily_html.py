"""Legacy YYYY-MM-DD.html generation from AIHOT items (template-based).

Ported from box inventory generators; no git/feishu side effects.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from .aihot_logic import classify_item, dedupe_by_title


def generate_top5_html(items: list[dict[str, Any]]) -> str:
    top5 = items[:5]
    if not top5:
        return ""
    html = '<section class="top5-section">\n  <div class="top5-header">\n'
    html += '    <span class="top5-title">Top 5 精选</span>\n    <span class="top5-badge">编辑精选</span>\n  </div>\n'
    for i, item in enumerate(top5, 1):
        summary = item.get("summary", item.get("reason", ""))
        html += '  <article class="top5-item">\n    <div class="top5-item-header">\n'
        html += f'      <div class="top5-item-rank">{i}</div>\n'
        html += f'      <div class="top5-item-title">{escape(item["title"])}</div>\n'
        html += f'      <span class="top5-item-score">{item["score"]}分</span>\n    </div>\n'
        html += f'    <div class="top5-item-source">{escape(item["src"])}</div>\n'
        html += f'    <div class="top5-item-summary">{escape(summary)}</div>\n'
        if item.get("link"):
            html += f'    <a href="{escape(item["link"])}" class="item-link" target="_blank">查看原文 &rarr;</a>\n'
        html += "  </article>\n"
    html += "</section>\n"
    return html


def generate_sections_html(items: list[dict[str, Any]]) -> str:
    unique_items = dedupe_by_title(items)
    categories: dict[str, list[dict[str, Any]]] = {}
    for item in unique_items:
        categories.setdefault(classify_item(item["title"]), []).append(item)
    order = ["模型发布/更新", "产品发布/更新", "行业动态", "论文研究", "技巧与观点"]
    html = ""
    for cat in order:
        cat_items = categories.get(cat)
        if not cat_items:
            continue
        html += '<section class="section">\n  <div class="section-header">\n'
        html += f'    <span class="section-title">{cat}</span>\n    <span class="section-count">{len(cat_items)} 条</span>\n  </div>\n'
        for i, item in enumerate(cat_items, 1):
            summary = item.get("summary", item.get("reason", ""))
            html += '  <article class="item">\n    <div class="item-header">\n'
            html += f'      <div class="item-num">{i}</div>\n'
            html += f'      <div class="item-title">{escape(item["title"])}</div>\n    </div>\n'
            html += f'    <div class="item-source">{escape(item["src"])} &middot; {item["score"]}分</div>\n'
            html += f'    <div class="item-summary">{escape(summary)}</div>\n'
            if item.get("link"):
                html += f'    <a href="{escape(item["link"])}" class="item-link" target="_blank">查看原文 &rarr;</a>\n'
            html += "  </article>\n"
        html += "</section>\n"
    return html


def generate_daily_html(target_date: date, items: list[dict[str, Any]], template: str) -> str:
    html = template.replace("{{DATE}}", target_date.strftime("%Y年%m月%d日"), 1)
    html = html.replace("{{DATE}}", target_date.strftime("%Y-%m-%d"), 1)
    html = html.replace(
        "{{LEAD}}",
        f"精选 {len(items)} 条 AI 行业动态，涵盖模型发布、产品更新、行业事件与前沿研究。",
    )
    html = html.replace("{{ITEM_COUNT}}", str(len(items)))
    html = html.replace("{{TOP5}}", generate_top5_html(items))
    html = html.replace("{{SECTIONS}}", generate_sections_html(items))
    # Older templates may still use {{FLASHES}}
    html = html.replace("{{FLASHES}}", "")
    return html


def verify_html_content(content: str) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for key in ("top5-section", "item-summary"):
        if key not in content:
            failed.append(key)
    empty = len(re.findall(r'<div class="item-summary"></div>', content))
    empty += len(re.findall(r'<div class="top5-item-summary"></div>', content))
    if empty > 0:
        failed.append(f"empty_summary:{empty}")
    empty_titles = len(re.findall(r'<div class="item-title"></div>', content))
    empty_titles += len(re.findall(r'<div class="top5-item-title"></div>', content))
    if empty_titles > 0:
        failed.append(f"empty_title:{empty_titles}")
    return (len(failed) == 0), failed


def write_daily_html(
    repo_root: Path,
    target_date: date,
    items: list[dict[str, Any]],
    *,
    template_path: Path | None = None,
) -> Path:
    template_path = template_path or (repo_root / "daily-template.html")
    template = template_path.read_text(encoding="utf-8")
    html = generate_daily_html(target_date, items, template)
    out = repo_root / f"{target_date.strftime('%Y-%m-%d')}.html"
    out.write_text(html, encoding="utf-8")
    ok, failed = verify_html_content(html)
    if not ok:
        raise ValueError(f"HTML verification failed: {failed}")
    return out
