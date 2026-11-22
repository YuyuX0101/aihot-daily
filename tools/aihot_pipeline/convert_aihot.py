"""Convert AIHOT raw items into unified daily-channel feed JSON."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .aihot_logic import classify_item, dedupe_by_title, stable_item_id

SHANGHAI = ZoneInfo("Asia/Shanghai")


def items_to_daily_feed(
    items: list[dict[str, Any]],
    *,
    edition_date: str | date,
    generated_at: str | None = None,
    source: str = "aihot-virxact",
) -> dict[str, Any]:
    if isinstance(edition_date, date):
        edition_date = edition_date.strftime("%Y-%m-%d")
    generated_at = generated_at or datetime.now(tz=SHANGHAI).isoformat(timespec="seconds")

    unique = dedupe_by_title(items)
    out_items: list[dict[str, Any]] = []
    for raw in unique:
        summary = (raw.get("summary") or raw.get("reason") or raw.get("title") or "").strip()
        tags = ["page_reachable", "untested"]
        # aihot scores are editorial AI scores, not "we played it"
        item = {
            "id": stable_item_id(raw),
            "title": raw.get("title") or "",
            "summary": summary[:2000],
            "source_url": raw.get("link") or None,
            "author": raw.get("src") or "",
            "published_at": None,
            "verified_at": generated_at,
            "verification_tags": tags,
            "notes": f"分类候选：{classify_item(raw.get('title') or '')}；来自 aihot 公开页筛选，未人工实测",
            "score": int(raw.get("score") or 0),
            "author_claim": "",
            "verified_evidence": summary[:2000],
        }
        # drop empties for cleaner JSON
        if not item["source_url"]:
            item.pop("source_url")
        if not item["author"]:
            item.pop("author")
        out_items.append(item)

    return {
        "schema_version": "1.0",
        "edition_date": edition_date,
        "channel": "daily",
        "source": source,
        "generated_at": generated_at,
        "items": out_items,
    }
