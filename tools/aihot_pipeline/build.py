"""Build static HTML pages from edition JSON. Does not touch historical YYYY-MM-DD.html."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .demo_guard import DemoGuardError, assert_edition_has_no_demo_urls
from .home import build_home, daily_archive
from .ingest import load_edition, refresh_editions_index
from .paths import (
    BUILDER_DIR,
    DAYS_JSON,
    DEALS_DIR,
    EDITION_HTML_DIR,
    EDITIONS_DIR,
    REPO_ROOT,
)
from .render import date_select, page_shell, project_grid, render_item
from .sanitize import escape_text, validate_url


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


def _entry_href(*urls: str | None) -> str:
    for url in urls:
        try:
            href = validate_url(url)
        except Exception:
            href = None
        if href:
            return href
    return ""


def _compact_entry(item: dict[str, Any], channel: str) -> str:
    title = item.get("title") or ""
    summary = (item.get("summary") or item.get("author_claim") or "").removeprefix(
        "【速报转载 · 未独立核验 · 未实测】"
    ).strip()
    if channel == "builder" and "：" in title:
        name, tagline = title.split("：", 1)
        if name.strip() and tagline.strip():
            title = name.strip()
            if not summary or summary == item.get("title"):
                summary = tagline.strip()
    href = _entry_href(item.get("playable_url"), item.get("source_url"))
    source_href = _entry_href(item.get("source_url")) if channel != "daily" else href
    if channel == "builder":
        source_label = "作者原帖"
        meta = item.get("author") or "独立开发者作品"
    elif channel == "daily":
        source_label = "原始来源" if item.get("playable_url") else "AIHOT 条目"
        meta = item.get("author") or "AIHOT"
        summary = ""
    else:
        source_label = "查看来源"
        meta = "优惠条件与适用期限见来源"
    title_html = escape_text(title)
    if href:
        title_html = (
            f'<a class="entry-title" href="{escape_text(href)}" target="_blank" '
            f'rel="noopener noreferrer"><strong>{title_html}</strong></a>'
        )
    else:
        title_html = f"<strong>{title_html}</strong>"
    summary_html = f'<span class="entry-summary">{escape_text(summary)}</span>' if summary else ""
    source_html = ""
    if source_href:
        source_html = (
            '<div class="entry-actions">'
            f'<a class="entry-source" href="{escape_text(source_href)}" target="_blank" '
            f'rel="noopener noreferrer">{source_label}</a></div>'
        )
    return (
        '<article class="desk-entry"><div class="entry-copy">'
        f'{title_html}{summary_html}<small class="entry-meta">{escape_text(meta)}</small>'
        f'{source_html}</div></article>'
    )


def _compact_section(
    channel: str,
    index: str,
    english: str,
    title: str,
    items: list[dict[str, Any]],
    empty_message: str,
) -> str:
    archive = {"daily": "../daily/index.html", "builder": "../builder/index.html", "deals": "../deals/index.html"}[channel]
    archive_label = {"daily": "全部日报", "builder": "全部作品", "deals": "全部优惠"}[channel]
    content = "".join(_compact_entry(item, channel) for item in items)
    if not items:
        content = f'<p class="empty-message">{escape_text(empty_message)}</p>'
    boundary = '<p class="reading-boundary">AIHOT 转载，未独立核验；刊期不等于原文发布时间。</p>' if channel == "daily" else ""
    return f'''<section id="{channel}" class="news-section desk-{channel}" aria-labelledby="{channel}-title">
<header class="section-heading"><div><p class="section-index">{index} / {english}</p><h2 id="{channel}-title">{title}</h2></div>
<div class="section-aside"><small class="item-total">{len(items)} 条</small><a class="archive-link" href="{archive}">{archive_label}</a></div></header>
{boundary}<div class="channel-content">{content}</div></section>'''


def build_edition_page(
    edition: dict[str, Any], available_dates: list[str] | None = None
) -> str:
    assert_edition_has_no_demo_urls(edition)
    date = edition["edition_date"]
    counts = _counts(edition)
    channels = edition.get("channels") or {}
    dates = available_dates or [date]

    legacy_same_day = ""
    legacy_path = REPO_ROOT / f"{date}.html"
    if legacy_path.exists():
        legacy_same_day = (
            f'<p class="legacy-note">同日历史日报：'
            f'<a href="../{escape_text(date)}.html">{escape_text(date)}.html</a></p>'
        )

    daily_items = (channels.get("daily") or {}).get("items") or []
    builder_items = (channels.get("builder") or {}).get("items") or []
    deals_items = (channels.get("deals") or {}).get("items") or []
    daily_empty = ((channels.get("daily") or {}).get("meta") or {}).get("empty_message") or "本期暂无 AI 动态。"
    builder_empty = "本期暂无作品记录。"
    deals_empty = ((channels.get("deals") or {}).get("meta") or {}).get("empty_message") or "本期暂无优惠记录。"
    daily = _compact_section("daily", "01", "DAILY", "AIHOT", daily_items, daily_empty)
    builder = _compact_section("builder", "02", "MAKERS", "AI Builder", builder_items, builder_empty)
    deals = _compact_section("deals", "03", "DEALS", "羊毛雷达", deals_items, deals_empty)
    daily_heavy = " daily-heavy" if counts["daily"] >= 7 and counts["daily"] > counts["builder"] else ""
    body = (
        f'<div class="page-toolbar">{date_select(dates, date, url_template="{date}.html")}</div>'
        f'<div class="reading-flow{daily_heavy}" aria-label="{escape_text(date)} 统一期次">'
        f'<div class="left-column">{daily}{deals}</div>{builder}</div>'
        '<nav class="section-dock" aria-label="跳至本期栏目"><a href="#daily">AIHOT</a>'
        '<a href="#builder">作品</a><a href="#deals">羊毛</a></nav>'
    )
    if legacy_same_day:
        body += "\n" + legacy_same_day

    lead = "AIHOT 动态、独立作品与优惠，按刊期完整归档。"
    return page_shell(
        title=f"AI 日报 · 统一期次 · {date}",
        kicker="统一期次",
        heading=f"{date}",
        lead=lead,
        body=body,
        active_nav="editions",
        css_href="../assets/editorial.css",
    )


def build_channel_index(channel: str, dates: list[str]) -> str:
    panels = []
    for index, date in enumerate(dates):
        edition = load_edition(date)
        bucket = (edition.get("channels") or {}).get(channel) or {}
        items = bucket.get("items") or []
        meta = bucket.get("meta") or {}
        if channel == "builder" and items:
            assert_edition_has_no_demo_urls(edition)
            content = project_grid(items, detailed=False)
        elif items:
            content = '<div class="article-list">' + "".join(render_item(item, channel) for item in items) + '</div>'
        else:
            message = meta.get("empty_message") or "本期暂无收录。"
            content = f'<p class="empty-state-inline">{escape_text(message)}</p>'
        hidden = "" if index == 0 else " hidden"
        panels.append(
            f'<section class="date-panel" data-date-panel="{escape_text(date)}"{hidden}>'
            f'<div class="date-panel-meta"><span>{escape_text(date)}</span><span>{len(items)} 条</span></div>'
            f'{content}</section>'
        )
    title = "AI Builder" if channel == "builder" else "羊毛雷达"
    if dates:
        toolbar = f'<div class="page-toolbar">{date_select(dates, dates[0])}</div>'
        body = toolbar + "\n".join(panels)
    else:
        body = '<p class="empty">暂无内容。将生产 JSON 放入 data/inbox/ 后运行 ingest + build。</p>'
    return page_shell(
        title=f"{title} · AI 日报",
        kicker="每日精选",
        heading=title,
        lead="作品、作者声明与体验入口。" if channel == "builder" else "优惠内容、门槛与适用条件。",
        body=body,
        active_nav=channel,
        css_href="../assets/editorial.css",
    )


def build_editions_index(dates: list[str]) -> str:
    if dates:
        return build_edition_page(load_edition(dates[0]), available_dates=dates)
    return page_shell(
        title="期次 · AI 日报",
        kicker="期次",
        heading="每日期次",
        lead="按日期阅读日报、AI Builder 作品与优惠。",
        body='<p class="empty">暂无统一期次。</p>',
        active_nav="editions",
        css_href="../assets/editorial.css",
    )


def update_days_json_from_legacy() -> list[str]:
    days = sorted(
        (p.stem for p in REPO_ROOT.glob("????-??-??.html")),
        reverse=True,
    )
    DAYS_JSON.write_text(json.dumps(days, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return days


def update_legacy_ui() -> None:
    paths = list(REPO_ROOT.glob("????-??-??.html"))
    template = REPO_ROOT / "daily-template.html"
    if template.exists():
        paths.append(template)
    for path in paths:
        html = path.read_text(encoding="utf-8")
        original = html
        html = re.sub(r'href="assets/favicon\.(?:svg|png)(?:\?v=\d+)?"', 'href="assets/favicon.png?v=1"', html)
        if "legacy-daily-overlay.css" not in html:
            html = html.replace(
                "</head>", '<link rel="stylesheet" href="assets/legacy-daily-overlay.css">\n</head>', 1
            )
        html = re.sub(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*', "", html)
        html = re.sub(r'<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">\s*', "", html)
        html = html.replace(
            'content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"',
            'content="width=device-width, initial-scale=1.0"',
        )
        html = html.replace("AI HOT 日报 ·", "AI 日报 ·")
        html = html.replace("<h1>AI HOT 日报</h1>", "<h1>AI 日报</h1>")
        html = html.replace(
            '<div class="nav-brand"><em>AI</em> <span>HOT</span></div>',
            '<div class="nav-brand">AI 日报</div>',
        )
        html = re.sub(r'assets/date-picker\.js(?:\?v=\d+)?', 'assets/date-picker.js?v=2', html)
        if "assets/date-picker.js" not in html:
            html = html.replace(
                "</head>", '<script src="assets/date-picker.js?v=2" defer></script>\n</head>', 1
            )
        if html != original:
            path.write_text(html, encoding="utf-8")


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

    edition_days = []
    for date in dates:
        edition = load_edition(date)
        try:
            html = build_edition_page(edition, available_dates=dates)
        except DemoGuardError as exc:
            errors.append(f"{date}: {exc}")
            continue
        if _counts(edition)["daily"]:
            edition_days.append(date)
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

    from .home_snapshot import build_home_snapshot

    snap = build_home_snapshot(dates)
    written.append("data/home_snapshot.json")

    legacy_days = update_days_json_from_legacy()
    update_legacy_ui()

    if not errors:
        archive_dir = REPO_ROOT / "daily"
        archive_dir.mkdir(exist_ok=True)
        (archive_dir / "index.html").write_text(daily_archive(legacy_days, edition_days), encoding="utf-8")
        (REPO_ROOT / "index.html").write_text(build_home(), encoding="utf-8")
        written.extend(["daily/index.html", "index.html"])
    return {
        "ok": len(errors) == 0,
        "edition_dates": dates,
        "written": written,
        "legacy_days": legacy_days,
        "home_snapshot": snap.get("edition_date"),
        "errors": errors,
    }
