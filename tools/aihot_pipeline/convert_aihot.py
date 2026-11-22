"""Convert AIHOT raw items / official daily reports into unified daily-channel feed JSON.

Honesty rules for third-party AIHOT aggregates:
  - Always tag as AIHOT 转载 / 未独立核验 — HTTP success ≠ fact verification.
  - Preserve upstream source.name and original URL; AIHOT attribution must not erase them.
  - Never emit verified/tested/played/audited; never treat URL presence as page_reachable proof.
  - Do not invent published_at when upstream omits it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .aihot_http import report_to_raw_items
from .aihot_logic import classify_item, dedupe_by_title, stable_item_id

SHANGHAI = ZoneInfo("Asia/Shanghai")

# Mandatory honesty tags for any AIHOT-sourced daily item.
AIHOT_IMPORT_TAGS = ["aihot_repost", "unverified_upstream", "untested", "hearsay"]

AIHOT_EVIDENCE_STUB = (
    "仅确认 AIHOT 公开 API/抓取返回该条目；未独立打开原文核验事实，"
    "也不把链接存在当作已读过或已证实。"
)


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
        upstream_summary = (raw.get("summary") or raw.get("reason") or "").strip()
        title = (raw.get("title") or "").strip()
        # Prefer real upstream name; AIHOT is aggregator attribution in notes/tags.
        upstream_name = (raw.get("src") or raw.get("source_name") or "").strip()
        aihot_item_url = (raw.get("aihot_url") or raw.get("link") or "").strip() or None
        original_url = (raw.get("original_url") or "").strip() or None
        # If only one URL exists, keep it as original when it is not an aihot host.
        if not original_url and aihot_item_url and "aihot.news" not in aihot_item_url and "aihot.virxact.com" not in aihot_item_url:
            original_url = aihot_item_url
            aihot_item_url = None

        notes_bits = [
            "AIHOT 转载 / 未独立核验",
            f"分类候选：{classify_item(title)}",
            "来自 aihot.news 公开日报 API（只读）"
            if source.startswith("aihot-news")
            else "来自 groups-file/离线抓取（仍为第三方汇总）",
            "链接可点开查阅，不等于本站已读过或证实其断言",
        ]
        if raw.get("section_label"):
            notes_bits.insert(1, f"上游栏目：{raw['section_label']}")
        if upstream_name:
            notes_bits.insert(1, f"上游来源名：{upstream_name}")

        raw_id = str(raw.get("id") or "")
        if raw_id.startswith("daily:"):
            item_id = raw_id
        elif raw_id:
            item_id = f"daily:{raw_id}"
        else:
            item_id = stable_item_id(raw)

        # Frame title/summary as upstream reporting, not our verified prose.
        claim = title
        if upstream_summary:
            claim = f"{title}\n\n上游摘要：{upstream_summary}"[:2000]

        published_at = raw.get("published_at")
        if published_at is not None and not str(published_at).strip():
            published_at = None

        framed_summary = (
            f"【上游报道 · AIHOT 转载 · 未独立核验】{(upstream_summary or title)}"
        )[:2000]
        item: dict[str, Any] = {
            "id": item_id,
            # Keep upstream headline text for display, but tags/notes forbid fact tone.
            "title": title,
            "summary": framed_summary,
            "author": upstream_name or "（上游来源未标注）",
            "published_at": published_at,
            # Ingest timestamp only — render labels it as 摄取, not 核查 for daily.
            "verified_at": generated_at,
            "verification_tags": list(AIHOT_IMPORT_TAGS),
            "notes": "；".join(notes_bits)[:500],
            "score": int(raw.get("score") or 0),
            "author_claim": claim[:2000],
            "verified_evidence": AIHOT_EVIDENCE_STUB,
        }
        # source_url = AIHOT attribution page when present; original stays playable_url.
        if aihot_item_url:
            item["source_url"] = aihot_item_url
        elif original_url:
            item["source_url"] = original_url
        if original_url and original_url != item.get("source_url"):
            item["playable_url"] = original_url
        if not item.get("source_url"):
            item.pop("source_url", None)

        out_items.append(item)

    channel_meta = {
        "honesty": "aihot_repost_unverified",
        "section_disclaimer": (
            "本栏目条目来自 AIHOT 第三方公开汇总（API 刊期 date=业务日）。"
            "API 刊期不等于原文发布时间；未提供 published_at 时不编造时间。"
            "标题与摘要均为上游报道转载，本站未独立核验其中的科学/安全等事实断言。"
        ),
    }
    if source_meta:
        channel_meta["source_meta"] = source_meta

    feed: dict[str, Any] = {
        "schema_version": "1.0",
        "edition_date": edition_date,
        "channel": "daily",
        "source": source,
        "generated_at": generated_at,
        "items": out_items,
        "channel_meta": channel_meta,
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
        "attribution": "AIHOT",
        "honesty": "third_party_aggregate_unverified",
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
