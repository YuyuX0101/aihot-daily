"""Idempotent inbox ingestion into per-day edition JSON."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .demo_guard import DemoGuardError, assert_production_feed
from .paths import ARCHIVE_DIR, EDITIONS_DIR, EDITIONS_INDEX, INBOX_DIR
from .validate import ValidationError, load_and_validate_file


def _item_rank(item: dict[str, Any], feed_generated_at: str) -> str:
    return item.get("verified_at") or feed_generated_at or ""


def _merge_channel(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    feed_generated_at: str,
) -> tuple[list[dict[str, Any]], int, int]:
    by_id: dict[str, dict[str, Any]] = {i["id"]: dict(i) for i in existing}
    added = 0
    updated = 0
    for item in incoming:
        item_id = item["id"]
        if item_id not in by_id:
            by_id[item_id] = dict(item)
            added += 1
            continue
        old = by_id[item_id]
        if _item_rank(item, feed_generated_at) >= _item_rank(old, feed_generated_at):
            by_id[item_id] = dict(item)
            updated += 1
    merged = sorted(
        by_id.values(),
        key=lambda x: (-int(x.get("score") or 0), x["id"]),
    )
    return merged, added, updated


def empty_channel() -> dict[str, Any]:
    return {"items": [], "sources": [], "meta": {}}


def load_edition(date: str) -> dict[str, Any]:
    path = EDITIONS_DIR / f"{date}.json"
    if not path.exists():
        return {
            "edition_date": date,
            "updated_at": None,
            "channels": {
                "daily": empty_channel(),
                "builder": empty_channel(),
                "deals": empty_channel(),
            },
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_edition(edition: dict[str, Any]) -> Path:
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    date = edition["edition_date"]
    path = EDITIONS_DIR / f"{date}.json"
    edition["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(edition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def refresh_editions_index() -> list[str]:
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    dates = sorted(
        (p.stem for p in EDITIONS_DIR.glob("*.json")),
        reverse=True,
    )
    EDITIONS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    EDITIONS_INDEX.write_text(
        json.dumps(dates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dates


def apply_feed(feed: dict[str, Any]) -> dict[str, Any]:
    assert_production_feed(feed)
    date = feed["edition_date"]
    channel = feed["channel"]
    edition = load_edition(date)
    channel_bucket = edition["channels"].setdefault(channel, empty_channel())
    merged, added, updated = _merge_channel(
        channel_bucket.get("items") or [],
        feed["items"],
        feed["generated_at"],
    )
    channel_bucket["items"] = merged
    sources = channel_bucket.setdefault("sources", [])
    src_entry = {
        "source": feed["source"],
        "generated_at": feed["generated_at"],
        "item_count": len(feed["items"]),
    }
    if src_entry not in sources:
        sources.append(src_entry)
    meta = channel_bucket.setdefault("meta", {})
    if feed.get("channel_meta"):
        meta.update(feed["channel_meta"])
    edition["channels"][channel] = channel_bucket
    path = save_edition(edition)
    return {
        "edition_date": date,
        "channel": channel,
        "added": added,
        "updated": updated,
        "total": len(merged),
        "path": str(path),
    }


def ensure_channel_meta(
    edition_date: str,
    channel: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Attach empty-state metadata without inventing items."""
    edition = load_edition(edition_date)
    bucket = edition["channels"].setdefault(channel, empty_channel())
    bucket.setdefault("meta", {}).update(meta)
    edition["channels"][channel] = bucket
    path = save_edition(edition)
    return {"edition_date": edition_date, "channel": channel, "path": str(path), "meta": meta}


def ingest_inbox(inbox: Path | None = None, archive: Path | None = None) -> dict[str, Any]:
    inbox = inbox or INBOX_DIR
    archive = archive or ARCHIVE_DIR
    inbox.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    files = sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() == ".json")
    for path in files:
        try:
            feed = load_and_validate_file(path, allow_demo=False)
            summary = apply_feed(feed)
            summary["file"] = path.name
            results.append(summary)
            dest = archive / path.name
            if dest.exists():
                dest = archive / f"{path.stem}-{datetime.now(timezone.utc).strftime('%H%M%S')}{path.suffix}"
            shutil.move(str(path), str(dest))
        except (ValidationError, DemoGuardError, OSError, json.JSONDecodeError) as exc:
            errors.append({"file": path.name, "error": str(exc)})

    dates = refresh_editions_index()
    return {
        "processed": results,
        "errors": errors,
        "edition_dates": dates,
        "ok": len(errors) == 0,
    }
