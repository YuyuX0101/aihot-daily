"""Build a static home_snapshot.json for the homepage first screen."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .build import _counts, latest_legacy_daily
from .ingest import load_edition
from .paths import DATA_DIR, REPO_ROOT
from .timefmt import format_beijing

HOME_SNAPSHOT = DATA_DIR / "home_snapshot.json"


def build_home_snapshot(dates: list[str]) -> dict[str, Any]:
    if not dates:
        snap = {
            "edition_date": None,
            "edition_url": "e/index.html",
            "counts": {"daily": 0, "builder": 0, "deals": 0},
            "builder_items": [],
            "deals_empty_message": "暂无统一期次。",
            "daily_empty_message": "暂无统一期次。",
            "legacy_daily_url": latest_legacy_daily(),
            "note": "预览站点：统一飞书发送与生产切流尚未启用。",
        }
    else:
        date = dates[0]
        edition = load_edition(date)
        channels = edition.get("channels") or {}
        builder_items = []
        for item in (channels.get("builder") or {}).get("items") or []:
            builder_items.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "author": item.get("author"),
                    "source_url": item.get("source_url"),
                    "playable_url": item.get("playable_url"),
                    "repo_url": item.get("repo_url"),
                    "published_beijing": format_beijing(item.get("published_at")),
                    "verification_tags": item.get("verification_tags") or [],
                }
            )
        deals_meta = ((channels.get("deals") or {}).get("meta") or {})
        daily_meta = ((channels.get("daily") or {}).get("meta") or {})
        legacy = f"{date}.html" if (REPO_ROOT / f"{date}.html").exists() else latest_legacy_daily()
        snap = {
            "edition_date": date,
            "edition_url": f"e/{date}.html",
            "counts": _counts(edition),
            "builder_items": builder_items,
            "deals_empty_message": deals_meta.get(
                "empty_message",
                "本期暂无同时满足新鲜度与可核验要求的优惠。",
            ),
            "daily_empty_message": daily_meta.get(
                "empty_message",
                "当日暂无 AI HOT 日报生成结果。",
            ),
            "legacy_daily_url": legacy,
            "daily_source_date": date,
            "daily_ingest_source": daily_meta.get("ingest_source"),
            "daily_official_page": (daily_meta.get("source_meta") or {}).get("official_page"),
            "note": (
                "网站预览：完整结果在期次页。"
                f"日报栏目日期={date}（AIHOT 第三方汇总转载，未独立核验）"
                + (
                    f"；官方页={(daily_meta.get('source_meta') or {}).get('official_page')}"
                    if (daily_meta.get("source_meta") or {}).get("official_page")
                    else ""
                )
                + "。统一飞书摘要发送与生产切流尚未启用。"
            ),
        }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HOME_SNAPSHOT.write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return snap
