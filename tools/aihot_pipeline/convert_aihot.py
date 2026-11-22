"""Convert AIHOT raw items / official daily reports into unified daily-channel feed JSON."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .aihot_http import report_to_raw_items
from .aihot_logic import classify_item, dedupe_by_title, stable_item_id

SHANGHAI = ZoneInfo("Asia/Shanghai")


def items_to_daily_feed(
    items: list[dict[str, Any]],
    *,
    edition_date: str | date,
    generated_at: str | None = None,
    source: str = "aihot-news-api",
    source_meta: dict[str, Any] | None = None,
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
        notes_bits = [
            f"分类候选：{classify_item(raw.get('title') or '')}",
            "来自 aihot.news 公开日报 API（只读）" if source.startswith("aihot-news") else "来自 groups-file/离线抓取",
            "未人工实测",
        ]
        if raw.get("section_label"):
            notes_bits.insert(0, f"官方栏目：{raw['section_label']}")
        raw_id = str(raw.get("id") or "")
        if raw_id.startswith("daily:"):
            item_id = raw_id
        elif raw_id:
            item_id = f"daily:{raw_id}"
        else:
            item_id = stable_item_id(raw)
        item = {
            "id": item_id,
            "title": raw.get("title") or "",
            "summary": summary[:2000],
            "source_url": raw.get("link") or None,
            "author": raw.get("src") or "",
            "published_at": None,
            "verified_at": generated_at,
            "verification_tags": tags,
            "notes": "；".join(notes_bits),
            "score": int(raw.get("score") or 0),
            "author_claim": "",
            "verified_evidence": summary[:2000],
        }
        if raw.get("original_url"):
            item["playable_url"] = raw["original_url"]
        # drop empties for cleaner JSON
        if not item["source_url"]:
            item.pop("source_url")
        if not item["author"]:
            item.pop("author")
        out_items.append(item)

    feed: dict[str, Any] = {
        "schema_version": "1.0",
        "edition_date": edition_date,
        "channel": "daily",
        "source": source,
        "generated_at": generated_at,
        "items": out_items,
    }
    if source_meta:
        feed["source_meta"] = source_meta
    return feed


def official_report_to_daily_feed(
    report: dict[str, Any],
    *,
    generated_at: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert /api/v1/dailies response report → daily feed. edition_date = report.date."""
    edition_date = str(report["date"])
    raw_items = report_to_raw_items(report)
    meta = {
        "aihot_daily_date": edition_date,
        "aihot_generated_at": report.get("generatedAt"),
        "window_start": report.get("windowStart"),
        "window_end": report.get("windowEnd"),
        "lead_title": ((report.get("lead") or {}).get("title")),
        "official_page": ((report.get("links") or {}).get("aihot"))
        or f"https://aihot.news/daily/{edition_date}",
        "ingest_mode": "public_http_api",
    }
    if evidence:
        meta["fetch_evidence"] = evidence
    return items_to_daily_feed(
        raw_items,
        edition_date=edition_date,
        generated_at=generated_at,
        source="aihot-news-api-v1-dailies",
        source_meta=meta,
    )
