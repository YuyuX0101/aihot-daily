"""Static navigation and today's two-column reading layout."""

from datetime import date
from html.parser import HTMLParser
from typing import Any

from .ingest import load_edition
from .paths import REPO_ROOT
from .render import date_select, page_shell
from .sanitize import escape_text, validate_url


class LegacyDailyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self._item: dict[str, str] | None = None
        self._capture: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "article" and "item" in classes:
            self._item = {"title": "", "summary": "", "source": "", "href": ""}
            return
        if self._item is None:
            return
        for field, class_name in (("title", "item-title"), ("summary", "item-summary"), ("source", "item-source")):
            if tag == "div" and class_name in classes:
                self._capture = field
                self._parts = []
        if tag == "a" and "item-link" in classes and not self._item["href"]:
            self._item["href"] = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._item is None:
            return
        if tag == "div" and self._capture:
            self._item[self._capture] = "".join(self._parts).strip()
            self._capture = None
            self._parts = []
        elif tag == "article":
            if self._item["title"]:
                self.items.append(self._item)
            self._item = None
            self._capture = None


def _legacy_items(day: str) -> list[dict[str, str]]:
    parser = LegacyDailyParser()
    parser.feed((REPO_ROOT / f"{day}.html").read_text(encoding="utf-8"))
    return parser.items


def _daily_item_html(item: dict[str, Any], day: str, index: int) -> str:
    link = ""
    href = None
    label = "AIHOT 条目"
    for candidate, candidate_label in ((item.get("playable_url"), "原始来源"), (item.get("source_url"), "AIHOT 条目")):
        try:
            href = validate_url(candidate)
        except Exception:
            href = None
        if href:
            label = candidate_label
            break
    if href:
        link = (
            f'<div class="item-links"><a class="item-link" href="{escape_text(href)}" '
            f'rel="noopener noreferrer" target="_blank">{label}</a></div>'
        )
    summary = (item.get("summary") or item.get("author_claim") or "").removeprefix(
        "【上游报道 · AIHOT 转载 · 未独立核验】"
    ).strip()
    return f'''<article class="item daily-reading-item" id="daily-{escape_text(day)}-{index}">
<h3 class="item-title">{escape_text(item.get("title"))}</h3>
<div class="item-meta"><span>{escape_text(item.get("author") or "AIHOT")}</span></div>
<p class="reading-copy">{escape_text(summary)}</p>{link}</article>'''


def _legacy_item_html(item: dict[str, str], day: str, index: int) -> str:
    link = ""
    try:
        href = validate_url(item.get("href"))
    except Exception:
        href = None
    if href:
        link = (
            f'<div class="item-links"><a class="item-link" href="{escape_text(href)}" '
            'rel="noopener noreferrer" target="_blank">AIHOT 条目</a></div>'
        )
    return f'''<article class="item daily-reading-item legacy-item" id="legacy-{escape_text(day)}-{index}">
<h3 class="item-title">{escape_text(item["title"])}</h3>
<div class="item-meta"><span>{escape_text(item.get("source"))}</span></div>
<p class="reading-copy">{escape_text(item.get("summary"))}</p>{link}</article>'''


def daily_archive(days: list[str], edition_days: list[str]) -> str:
    dates = sorted(set(days) | set(edition_days), reverse=True)
    edition_set = set(edition_days)
    panels = []
    for index, day in enumerate(dates):
        if day in edition_set:
            edition = load_edition(day)
            bucket = (edition.get("channels") or {}).get("daily") or {}
            items = bucket.get("items") or []
            content = '<div class="article-list">' + "".join(
                _daily_item_html(item, day, item_index) for item_index, item in enumerate(items, 1)
            ) + '</div>'
            count = len(items)
        else:
            legacy_items = _legacy_items(day)
            content = '<div class="article-list">' + "".join(
                _legacy_item_html(item, day, item_index) for item_index, item in enumerate(legacy_items, 1)
            ) + '</div>'
            count = len(legacy_items)
        if not count:
            content = '<p class="empty-state-inline">本期暂无日报记录。</p>'
        hidden = "" if index == 0 else " hidden"
        panels.append(
            f'<section class="date-panel" data-date-panel="{escape_text(day)}"{hidden}>'
            f'<div class="date-panel-meta"><span>{escape_text(day)}</span><span>{count} 条</span></div>'
            '<p class="reading-boundary">内容为 AIHOT 转载，未独立核验。</p>'
            f'{content}</section>'
        )
    body = ""
    if dates:
        body += (
            f'<div class="page-toolbar">{date_select(dates, dates[0])}'
            '<p class="issue-overview">默认展示最新一期，选择日期阅读往期。</p></div>'
        ) + "".join(panels)
    else:
        body = '<p class="empty">暂无日报。</p>'
    return page_shell(title="AI 日报", kicker="每日精选", heading="AI 日报",
                      lead="AI 行业动态、产品更新与前沿研究。",
                      body=body, active_nav="daily")


def build_home() -> str:
    sections = {}
    for key, index, english, title, archive, label in (
        ("daily", "01", "DAILY", "AIHOT", "daily/index.html", "全部日报"),
        ("builder", "02", "MAKERS", "AI Builder", "builder/index.html", "全部作品"),
        ("deals", "03", "DEALS", "羊毛雷达", "deals/index.html", "全部优惠"),
    ):
        sections[key] = f"""
<section id="{key}" class="news-section desk-{key}" tabindex="-1" aria-labelledby="{key}-title">
  <header class="section-heading">
    <div><p class="section-index">{index} / {english}</p><h2 id="{key}-title">{title}</h2></div>
    <div class="section-aside"><small class="item-total"></small><a class="archive-link" href="{archive}">{label}</a></div>
  </header>
  <div class="channel-content" aria-live="polite"><p>正在读取当日内容…</p></div>
</section>"""
    body = """
<section class="cover" aria-labelledby="cover-title">
  <img id="cover-image" class="cover-image" src="assets/covers/2026-11-28.webp" alt="" width="2048" height="896" fetchpriority="high">
  <div class="cover-copy">
    <time id="business-day" class="issue-date">北京时间</time>
    <h1 id="cover-title">AI 日报</h1>
    <p class="cover-deck">今天值得关注的 AI 新知、作品与优惠。</p>
  </div>
</section>
<div id="today" class="reading-flow" aria-label="今日统一期次">
""" + '<div class="left-column">' + sections["daily"] + sections["deals"] + '</div>' + sections["builder"] + """</div>
<nav class="section-dock" aria-label="跳至本期栏目"><a href="#daily">AIHOT</a><a href="#builder">作品</a><a href="#deals">羊毛</a></nav>
<noscript>请启用 JavaScript 查看北京时间当天的内容，或使用各栏目归档入口。</noscript>
<script src="assets/today.js?v=10" defer></script>"""
    return page_shell(title="AI 日报 · 每日新知", kicker="", heading="", lead="", body=body,
                      active_nav="home", css_href="assets/editorial.css", home_href="index.html")
