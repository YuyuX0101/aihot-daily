"""Pure AIHOT selection / classify / dedup logic (extracted from box inventory generators).

No browser, no git, no Feishu. Safe for offline unit tests.
Source of truth for business rules: vendor/box-inventory/aihot-daily-generator.py
(box copy ≈2026-11-18; not claimed to match current HP).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
SCORE_THRESHOLD = 75

CATEGORY_MAP = {
    "模型发布/更新": [
        "模型", "开源", "发布", "GPT", "Claude", "Gemini", "DeepSeek", "Grok",
        "Llama", "Mistral", "Qwen", "Kimi", "Ornith", "VibeThinker",
    ],
    "产品发布/更新": [
        "产品", "上线", "推出", "发布", "API", "App", "应用", "输入法", "工具", "平台",
    ],
    "行业动态": [
        "收购", "合并", "融资", "IPO", "上市", "监管", "政策", "法案", "诉讼", "起诉",
        "利润", "财报", "市场", "行业",
    ],
    "论文研究": ["论文", "研究", "arxiv", "预印本", "benchmark", "评测", "数据集"],
    "技巧与观点": ["教程", "技巧", "提示词", "prompt", "观点", "评测", "体验", "指南"],
}


def shanghai_today(now: datetime | None = None) -> date:
    now = now or datetime.now(tz=SHANGHAI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI).date()


def default_target_date(now: datetime | None = None) -> date:
    """HP/box behavior: generate yesterday's content (Beijing calendar)."""
    return shanghai_today(now) - __import__("datetime").timedelta(days=1)


def parse_day_label(day_str: str, *, today: date | None = None) -> tuple[int | None, int | None]:
    if day_str == "今天":
        today = today or shanghai_today()
        return today.month, today.day
    m = re.match(r"(\d+)月(\d+)日", day_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def filter_target_items(
    groups: list[dict[str, Any]],
    target: date,
    *,
    score_threshold: int = SCORE_THRESHOLD,
    today: date | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for g in groups:
        day_str = g.get("day", "")
        month, day = parse_day_label(day_str, today=today)
        if month == target.month and day == target.day:
            for r in g.get("rows", []):
                try:
                    score = int(r.get("score", "0") or 0)
                except (TypeError, ValueError):
                    score = 0
                if score >= score_threshold:
                    items.append(
                        {
                            "title": r.get("title", "") or "",
                            "score": score,
                            "src": r.get("src", "") or "",
                            "link": r.get("link", "") or "",
                            "reason": r.get("reason", "") or "",
                            "summary": r.get("summary", "") or "",
                            "time": r.get("time", "") or "",
                        }
                    )
    items.sort(key=lambda x: (-x["score"], x["title"]))
    return items


def dedupe_by_title(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        title = item.get("title") or ""
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(item)
    return out


def classify_item(title: str) -> str:
    title_lower = (title or "").lower()
    best_cat, best_score = "行业动态", 0
    for cat, keywords in CATEGORY_MAP.items():
        score = sum(kw.lower() in title_lower for kw in keywords)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat


def stable_item_id(item: dict[str, Any]) -> str:
    link = (item.get("link") or "").strip()
    if link:
        # Prefer trailing /items/<id> when present.
        m = re.search(r"/items/([^/?#]+)", link)
        if m:
            return f"daily:{m.group(1)}"
        import hashlib

        return "daily:" + hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    import hashlib

    base = f"{item.get('title','')}|{item.get('src','')}|{item.get('score',0)}"
    return "daily:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
