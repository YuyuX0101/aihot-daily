"""Convert parent-bot builder first-run JSON into v1 feed items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def convert_item(raw: dict[str, Any]) -> dict[str, Any]:
    author = raw.get("author_name") or ""
    username = raw.get("username") or ""
    if username:
        author = f"{author} (@{username})" if author else f"@{username}"

    tags = ["page_reachable", "author_claim", "untested"]
    if raw.get("repo_url"):
        tags.append("repo_reachable")

    notes_bits = ["未实际实玩"]
    # Explicit honesty for claims that page-open ≠ audit.
    title = raw.get("title") or ""
    if "CPU" in title or "3nm" in title:
        notes_bits.append("倍率等能力为作者声明；页可打开≠功能审计")
    if "TextVeil" in title or "文隐" in title:
        notes_bits.append("「本地不上传」为作者声明；页可打开≠隐私审计")

    item: dict[str, Any] = {
        "id": f"builder:{raw['id']}",
        "title": raw["title"],
        "summary": raw.get("verified") or "",
        "source_url": raw.get("post_url"),
        "playable_url": raw.get("playable_url"),
        "author": author,
        "published_at": raw.get("posted_at_utc") or raw.get("posted_at_shanghai"),
        "verified_at": None,  # filled by caller
        "author_claim": raw.get("author_claim") or "",
        "verified_evidence": raw.get("verified") or "",
        "verification_tags": tags,
        "notes": "；".join(notes_bits),
        "score": 50,
    }
    if raw.get("repo_url"):
        item["repo_url"] = raw["repo_url"]
    return item


def convert_report(report: dict[str, Any], edition_date: str) -> dict[str, Any]:
    generated_at = report.get("generated_at") or ""
    items = []
    for raw in report.get("items") or []:
        item = convert_item(raw)
        item["verified_at"] = generated_at
        items.append(item)
    # Prefer newer posts in summary ranking without inventing engagement.
    items.sort(key=lambda x: x.get("published_at") or "")
    for i, item in enumerate(items):
        item["score"] = 50 + i
    return {
        "schema_version": "1.0",
        "edition_date": edition_date,
        "channel": "builder",
        "source": "bot-x-web",
        "generated_at": generated_at if "T" in generated_at else generated_at + "T00:00:00+08:00",
        "items": items,
    }


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("report_json")
    p.add_argument("--edition-date", required=True)
    p.add_argument("-o", "--output", required=True)
    args = p.parse_args()
    report = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    feed = convert_report(report, args.edition_date)
    # Normalize generated_at to ISO with offset if needed
    Path(args.output).write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
