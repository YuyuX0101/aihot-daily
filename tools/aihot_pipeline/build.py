"""Build static HTML pages from edition JSON. Does not touch historical YYYY-MM-DD.html."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .demo_guard import DemoGuardError, assert_edition_has_no_demo_urls
from .ingest import load_edition, refresh_editions_index
from .paths import (
    BUILDER_DIR,
    DAYS_JSON,
    DEALS_DIR,
    EDITION_HTML_DIR,
    EDITIONS_DIR,
    REPO_ROOT,
)
from .render import CHANNEL_TITLES, page_shell, render_channel_section
from .sanitize import escape_text


def _counts(edition: dict[str, Any]) -> dict[str, int]:
    channels = edition.get("channels") or {}
    return {
        key: len((channels.get(key) or {}).get("items") or [])
        for key in ("daily", "builder", "deals")
    }


def latest_legacy_daily(before_or_on: str | None = None) -> str | None:
    days = sorted(
        (p.stem for p in REPO_ROOT.glob("????-??-??.html")),
        reverse=True,
    )
    if before_or_on:
        days = [d for d in days if d <= before_or_on]
    return days[0] if days else None


def build_edition_page(edition: dict[str, Any]) -> str:
    assert_edition_has_no_demo_urls(edition)
    date = edition["edition_date"]
    counts = _counts(edition)
    channels = edition.get("channels") or {}

    tabs = [
        f'<a href="#daily">日报 {counts["daily"]}</a>',
        f'<a href="#builder">Builder {counts["builder"]}</a>',
        f'<a href="#deals">羊毛 {counts["deals"]}</a>',
    ]

    legacy_same_day = ""
    legacy_path = REPO_ROOT / f"{date}.html"
    legacy_href_for_empty = None
    if legacy_path.exists():
        legacy_same_day = (
            f'<p class="legacy-note">同日历史日报页仍保留：'
            f'<a href="../{escape_text(date)}.html">{escape_text(date)}.html</a>'
            f"（原 URL 不变）</p>"
        )
        legacy_href_for_empty = f"../{date}.html"
    else:
        latest = latest_legacy_daily(before_or_on=date)
        if latest:
            legacy_href_for_empty = f"../{latest}.html"

    sections = []
    for ch in ("daily", "builder", "deals"):
        bucket = channels.get(ch) or {}
        sections.append(
            render_channel_section(
                ch,
                bucket.get("items") or [],
                meta=bucket.get("meta") or {},
                legacy_daily_href=legacy_href_for_empty if ch == "daily" else None,
            )
        )

    body = f'<div class="channel-tabs">{"".join(tabs)}</div>\n' + "\n".join(sections)
    if legacy_same_day:
        body += "\n" + legacy_same_day

    lead = (
        "本页汇总当日 AI HOT 日报、Builder 一手作品与 AI 羊毛雷达。"
        "标签区分「作者声明 / 页面可达 / 未实测」；页可打开不等于功能或隐私审计。"
    )
    return page_shell(
        title=f"AIHOT 统一期次 · {date}",
        kicker="统一期次",
        heading=f"{date}",
        lead=lead,
        body=body,
        active_nav="editions",
        css_href="../assets/site.css",
    )


def build_channel_index(channel: str, dates: list[str]) -> str:
    cards = []
    for date in dates:
        edition = load_edition(date)
        bucket = (edition.get("channels") or {}).get(channel) or {}
        items = bucket.get("items") or []
        meta = bucket.get("meta") or {}
        if items:
            top = items[0].get("title", "")
            cards.append(
                f'<a class="list-card" href="../e/{escape_text(date)}.html#{escape_text(channel)}">'
                f'<div class="date">{escape_text(date)}</div>'
                f'<div>{escape_text(top)}</div>'
                f'<div class="meta">{len(items)} 条 · 查看期次</div>'
                f"</a>"
            )
        elif meta.get("empty_message"):
            # Surface zero-item days with an explicit reason (e.g. deals=0).
            cards.append(
                f'<a class="list-card is-empty" href="../e/{escape_text(date)}.html#{escape_text(channel)}">'
                f'<div class="date">{escape_text(date)}</div>'
                f'<div>0 条</div>'
                f'<div class="meta">{escape_text(meta.get("empty_message"))}</div>'
                f"</a>"
            )
    if not cards:
        body = '<p class="empty">暂无内容。将生产 JSON 放入 data/inbox/ 后运行 ingest + build。</p>'
    else:
        body = "\n".join(cards)
    title = CHANNEL_TITLES[channel]
    return page_shell(
        title=title,
        kicker="栏目",
        heading=title,
        lead="按日期浏览该栏目；空栏目会标明原因，不会用示例条目充数。",
        body=body,
        active_nav=channel if channel in {"builder", "deals"} else "daily",
        css_href="../assets/site.css",
    )


def build_editions_index(dates: list[str]) -> str:
    cards = []
    for date in dates:
        edition = load_edition(date)
        c = _counts(edition)
        cards.append(
            f'<a class="list-card" href="{escape_text(date)}.html">'
            f'<div class="date">{escape_text(date)}</div>'
            f'<div>统一期次</div>'
            f'<div class="meta">日报 {c["daily"]} · Builder {c["builder"]} · 羊毛 {c["deals"]}</div>'
            f"</a>"
        )
    body = "\n".join(cards) if cards else '<p class="empty">暂无统一期次</p>'
    return page_shell(
        title="AIHOT 统一期次",
        kicker="目录",
        heading="统一期次",
        lead="每日一期，汇总三个栏目。历史 YYYY-MM-DD.html 日报 URL 继续可用。示例 fixtures 不会进入此目录。",
        body=body,
        active_nav="editions",
        css_href="../assets/site.css",
    )


def update_days_json_from_legacy() -> list[str]:
    days = sorted(
        (p.stem for p in REPO_ROOT.glob("????-??-??.html")),
        reverse=True,
    )
    DAYS_JSON.write_text(json.dumps(days, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return days


def build_site() -> dict[str, Any]:
    EDITION_HTML_DIR.mkdir(parents=True, exist_ok=True)
    BUILDER_DIR.mkdir(parents=True, exist_ok=True)
    DEALS_DIR.mkdir(parents=True, exist_ok=True)
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove stale edition HTML whose JSON was deleted (e.g. purged demo days).
    json_dates = {p.stem for p in EDITIONS_DIR.glob("*.json")}
    for html in EDITION_HTML_DIR.glob("????-??-??.html"):
        if html.stem not in json_dates:
            html.unlink()

    dates = refresh_editions_index()
    written: list[str] = []
    errors: list[str] = []

    for date in dates:
        edition = load_edition(date)
        try:
            html = build_edition_page(edition)
        except DemoGuardError as exc:
            errors.append(f"{date}: {exc}")
            continue
        out = EDITION_HTML_DIR / f"{date}.html"
        out.write_text(html, encoding="utf-8")
        try:
            written.append(str(out.relative_to(REPO_ROOT)))
        except ValueError:
            written.append(str(out))

    (EDITION_HTML_DIR / "index.html").write_text(build_editions_index(dates), encoding="utf-8")
    (BUILDER_DIR / "index.html").write_text(build_channel_index("builder", dates), encoding="utf-8")
    (DEALS_DIR / "index.html").write_text(build_channel_index("deals", dates), encoding="utf-8")
    written.extend(["e/index.html", "builder/index.html", "deals/index.html"])

    legacy_days = update_days_json_from_legacy()
    return {
        "ok": len(errors) == 0,
        "edition_dates": dates,
        "written": written,
        "legacy_days": legacy_days,
        "errors": errors,
    }
