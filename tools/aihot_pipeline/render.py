"""HTML rendering helpers — editorial shell; all dynamic text escaped; Beijing time."""

from __future__ import annotations

from typing import Any

from .sanitize import escape_text, validate_url
from .timefmt import format_beijing

CHANNEL_TITLES = {
    "daily": "AI 日报 · AI 动态",
    "builder": "Builder 一手作品速报",
    "deals": "AI 羊毛雷达",
}

PAGE_COVERS = {
    "daily": "page-daily.webp",
    "builder": "page-builder.webp",
    "deals": "page-deals.webp",
    "editions": "page-editions.webp",
}

# Editorial descriptions of the November 22 projects.
# New projects use the title, description and creator supplied by their feed.
PROJECT_DESCRIPTIONS = {
    "builder:2124333271177908405": ("文档工具", "据作者介绍，文隐可以在本地为文档脱敏，方便在交给 AI 之前处理敏感信息。"),
    "builder:2124265810663244086": ("交互模拟", "作者把 3nm 芯片做成了可缩放的三维模型，让人从外观一路探索到处理器内部。"),
    "builder:2124194668015661346": ("经营游戏", "从车库里的一间 AI 实验室起步。作者把芯片、算力与能源做进了一款浏览器经营游戏。"),
    "builder:2124161720448893216": ("对战游戏", "一位开发者和孩子一起做的格斗游戏。按作者介绍，玩家可以扮演不同的 AI 公司负责人。"),
    "builder:2124141427672134013": ("太空探索", "在浏览器里驾驶飞船、降落行星。作者介绍，这次更新给外星居民加入了对话功能。"),
}

DEFAULT_EMPTY = {
    "daily": "当日暂无 AI 动态；请查看最近历史日报，勿将示例内容当作当日资讯。",
    "builder": "本期暂无 Builder 条目。",
    "deals": "本期暂无羊毛条目。",
}


def date_select(dates: list[str], current: str, *, url_template: str | None = None) -> str:
    days = sorted(set(dates) | {current}, reverse=True)
    options = "".join(
        f'<option value="{escape_text(day)}"{" selected" if day == current else ""}>{escape_text(day)}</option>'
        for day in days
    )
    navigation = f' data-url-template="{escape_text(url_template)}"' if url_template else ""
    return (
        '<label class="date-picker"><span>日期</span>'
        f'<select data-date-picker{navigation} aria-label="选择内容日期">{options}</select></label>'
    )


def _safe_link(url: str | None, label: str) -> str:
    if not url:
        return ""
    try:
        safe = validate_url(url)
    except Exception:
        return ""
    if not safe:
        return ""
    return (
        f'<a class="item-link" href="{escape_text(safe)}" '
        f'rel="noopener noreferrer" target="_blank">{escape_text(label)}</a>'
    )


def project_card(item: dict[str, Any], *, detailed: bool = False) -> str:
    title = item.get("title") or ""
    category, intro = PROJECT_DESCRIPTIONS.get(
        item.get("id"), ("", item.get("summary") or item.get("author_claim") or "")
    )
    name = title
    intro = intro.removeprefix("【速报转载 · 未独立核验 · 未实测】").lstrip()
    project_name, separator, tagline = title.partition("：")
    if separator and project_name.strip() and tagline.strip():
        name = project_name.strip()
        if intro.strip() == title:
            intro = tagline.strip()
    links = "".join([
        _safe_link(item.get("playable_url"), "打开作品"),
        _safe_link(item.get("source_url"), "作者原帖"),
        _safe_link(item.get("repo_url"), "代码仓库"),
    ])
    published = format_beijing(item.get("published_at"))
    details = ""
    if detailed:
        facts = [
            ("作者声明", item.get("author_claim")),
            ("核验正文证据", item.get("verified_evidence")),
            ("备注", item.get("notes")),
        ]
        parts = [f'<p><strong>{label}</strong>　{escape_text(value)}</p>' for label, value in facts if value]
        if "page_reachable" in (item.get("verification_tags") or []):
            parts.append("<p>页面可达仅指采集时可以打开链接。</p>")
        if parts:
            details = '<details><summary>查看来源说明</summary>' + "".join(parts) + "</details>"
    anchor = f' id="{escape_text(item["id"])}"' if detailed and item.get("id") else ""
    return f'''<article class="project"{anchor}>
<div class="project-body"><div class="project-kind">{escape_text(category)}</div>
<h3>{escape_text(name)}</h3><p class="intro">{escape_text(intro)}</p>
<div class="creator">{escape_text(item.get("author") or "")}<small>{escape_text(published)}</small></div>
<div class="actions">{links}</div>{details}</div></article>'''


def project_grid(items: list[dict[str, Any]], *, detailed: bool = False) -> str:
    if not items:
        return '<p class="empty">本期暂无 Builder 作品。</p>'
    return '<div class="project-grid">' + "".join(project_card(i, detailed=detailed) for i in items) + '</div>'


def render_item(item: dict[str, Any], channel: str) -> str:
    if channel == "builder":
        return project_card(item, detailed=True)
    title = escape_text(item.get("title"))
    author = escape_text(item.get("author") or "")
    notes = escape_text(item.get("notes") or "")
    published = format_beijing(item.get("published_at") or "")
    verified = format_beijing(item.get("verified_at") or "")
    is_daily = channel == "daily"

    meta_parts = []
    if author:
        if is_daily:
            meta_parts.append(f"<span>上游来源 {author}</span>")
            meta_parts.append("<span>经 AIHOT 转载（未独立核验）</span>")
        else:
            meta_parts.append(f"<span>作者 {author}</span>")
    if published:
        meta_parts.append(f"<span>原文发布 {escape_text(published)}</span>")
    elif is_daily:
        meta_parts.append("<span>原文发布时间未知（未编造）</span>")
    if verified:
        meta_parts.append(
            f"<span>{'摄取' if is_daily else '核查'} {escape_text(verified)}</span>"
        )
    meta_html = f'<div class="item-meta">{"".join(meta_parts)}</div>' if meta_parts else ""

    claim = item.get("author_claim") or ""
    # For daily: never fall back to summary as "核验证据" — that would overclaim.
    if is_daily:
        evidence = item.get("verified_evidence") or ""
        claim_label = "上游报道（AIHOT 转载 · 未独立核验）"
        evidence_label = "本站核验边界"
    else:
        evidence = item.get("verified_evidence") or item.get("summary") or ""
        claim_label = "作者声明"
        evidence_label = "核验正文证据"
    blocks = []
    if claim:
        blocks.append(
            f'<div class="claim-box"><div class="box-label">{escape_text(claim_label)}</div>'
            f"<div>{escape_text(claim)}</div></div>"
        )
    if evidence:
        blocks.append(
            f'<div class="evidence-box"><div class="box-label">{escape_text(evidence_label)}</div>'
            f"<div>{escape_text(evidence)}</div></div>"
        )

    notes_html = f'<div class="item-notes">备注：{notes}</div>' if notes else ""

    deal_html = ""
    deal = item.get("deal") if channel == "deals" else None
    if deal:
        rows = []
        if deal.get("threshold"):
            rows.append(f"<div>门槛：{escape_text(deal['threshold'])}</div>")
        if deal.get("deadline"):
            rows.append(
                f"<div>截止：{escape_text(format_beijing(deal['deadline']) or deal['deadline'])}</div>"
            )
        if deal.get("regions"):
            regions = "、".join(escape_text(r) for r in deal["regions"])
            rows.append(f"<div>地区：{regions}</div>")
        if deal.get("restrictions"):
            rows.append(f"<div>限制：{escape_text(deal['restrictions'])}</div>")
        if rows:
            deal_html = f'<div class="deal-box">{"".join(rows)}</div>'

    if is_daily:
        link_specs = (
            (item.get("source_url"), "AIHOT 条目"),
            (item.get("playable_url"), "原文链接（未核验）"),
            (item.get("repo_url"), "仓库"),
        )
    else:
        link_specs = (
            (item.get("source_url"), "来源帖"),
            (item.get("playable_url"), "可打开页面"),
            (item.get("repo_url"), "仓库"),
        )
    links = []
    for url, label in link_specs:
        part = _safe_link(url, label)
        if part:
            links.append(part)
    link_html = f'<div class="item-links">{"".join(links)}</div>' if links else ""

    return f"""
<article class="item" id="{escape_text(item.get('id') or '')}">
  <h3 class="item-title">{title}</h3>
{meta_html}
{"".join(blocks)}
{deal_html}
{notes_html}
{link_html}
</article>
""".strip()


def render_channel_section(
    channel: str,
    items: list[dict[str, Any]],
    *,
    meta: dict[str, Any] | None = None,
    legacy_daily_href: str | None = None,
) -> str:
    title = CHANNEL_TITLES.get(channel, channel)
    meta = meta or {}
    count = len(items)
    empty = count == 0

    disclaimer = ""
    if channel == "daily":
        text = meta.get("section_disclaimer") or (
            "本栏目为 AIHOT 第三方汇总转载：API 刊期是业务日，不等于原文发布时间；"
            "未提供发布时间时不编造。标题与摘要为上游报道，未独立核验事实断言。"
        )
        disclaimer = f'<p class="section-disclaimer">{escape_text(text)}</p>'

    if empty:
        message = meta.get("empty_message") or DEFAULT_EMPTY.get(channel, "本期暂无条目。")
        extra = ""
        if channel == "daily" and legacy_daily_href:
            extra = (
                f'<p class="empty-link">最近历史日报：'
                f'<a href="{escape_text(legacy_daily_href)}">{escape_text(legacy_daily_href.split("/")[-1])}</a>'
                f"</p>"
            )
        body = f'<div class="empty-state-box"><p class="empty">{escape_text(message)}</p>{extra}</div>'
        collapsed_attr = ' class="section is-empty"'
    else:
        body = project_grid(items, detailed=True) if channel == "builder" else "\n".join(render_item(i, channel) for i in items)
        collapsed_attr = ' class="section"'

    return f"""
<section{collapsed_attr} id="{escape_text(channel)}">
  <div class="section-header">
    <span class="section-title">{escape_text(title)}</span>
    <span class="section-count">{count} 条</span>
  </div>
{disclaimer}
{body}
</section>
""".strip()


def page_shell(
    *,
    title: str,
    kicker: str,
    heading: str,
    lead: str,
    body: str,
    active_nav: str,
    css_href: str = "../assets/editorial.css",
    home_href: str = "../index.html",
    demo_banner: str | None = None,
) -> str:
    if css_href.startswith("assets/"):
        nav = {
            "home": ("首页", "index.html"),
            "daily": ("日报", "daily/index.html"),
            "builder": ("AI Builder", "builder/index.html"),
            "deals": ("羊毛", "deals/index.html"),
            "editions": ("期次", "e/index.html"),
        }
    else:
        nav = {
            "home": ("首页", home_href),
            "daily": ("日报", "../daily/index.html"),
            "builder": ("AI Builder", "../builder/index.html"),
            "deals": ("羊毛", "../deals/index.html"),
            "editions": ("期次", "../e/index.html"),
        }

    links = []
    for key, (label, href) in nav.items():
        current = ' aria-current="page"' if key == active_nav else ""
        cls = ' class="active"' if key == active_nav else ""
        links.append(
            f'<a{cls}{current} href="{href}">{escape_text(label)}</a>'
        )

    banner = ""
    if demo_banner:
        banner = (
            f'<div class="demo-banner" role="status">'
            f"<strong>示例预览</strong> — {escape_text(demo_banner)}"
            f"</div>"
        )

    is_home = active_nav == "home"
    page_class = "home" if is_home else "page page-wide"
    heading_html = "" if is_home else (
        f'<header class="inner-heading"><p class="section-meta">{escape_text(kicker)}</p>'
        f'<h1>{escape_text(heading)}</h1><p class="page-lead">{escape_text(lead)}</p></header>'
    )
    cover_name = PAGE_COVERS.get(active_nav)
    if not is_home and cover_name:
        cover_href = f"{css_href.rsplit('/', 1)[0]}/covers/{cover_name}"
        heading_html = (
            f'<section class="inner-hero"><img class="inner-cover-image" src="{cover_href}" '
            f'alt="" width="2048" height="688">{heading_html}</section>'
        )
    snapshot_link = '<link rel="alternate" type="application/json" href="data/home_snapshot.json">' if is_home else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_text(title)}</title>
<link rel="stylesheet" href="{css_href}?v=ai-daily-12">
<link rel="icon" type="image/png" href="{css_href.rsplit('/', 1)[0]}/favicon.png?v=1">
{snapshot_link}
</head>
<body>
<a class="skip-link" href="#main">跳到正文</a>
<header class="site-header">
  <div class="site-header-inner">
    <a class="brand" href="{nav['home'][1]}" aria-label="AI 日报首页"><span class="brand-name">AI 日报</span><span class="brand-en">AI DAILY</span></a>
    <nav class="nav-links" id="site-nav" aria-label="主导航">
      {''.join(links)}
    </nav>
  </div>
</header>
{banner}
<main class="{page_class}" id="main">
{heading_html}
{body}
</main>
<script src="{css_href.rsplit('/', 1)[0]}/date-picker.js?v=2" defer></script>
</body>
</html>
"""
