"""HTML rendering helpers — all dynamic text is escaped."""

from __future__ import annotations

from typing import Any

from .sanitize import escape_text, validate_url


CHANNEL_TITLES = {
    "daily": "AI HOT 日报",
    "builder": "Builder 一手作品速报",
    "deals": "AI 羊毛雷达",
}


def _tags_html(tags: list[str] | None) -> str:
    if not tags:
        return ""
    bits = []
    for t in tags:
        cls = "tag warn" if t in {"untested", "hearsay"} else "tag"
        bits.append(f'<span class="{cls}">{escape_text(t)}</span>')
    return " ".join(bits)


def render_item(item: dict[str, Any], channel: str) -> str:
    title = escape_text(item.get("title"))
    summary = escape_text(item.get("summary") or "")
    author = escape_text(item.get("author") or "")
    notes = escape_text(item.get("notes") or "")
    published = escape_text(item.get("published_at") or "")
    verified = escape_text(item.get("verified_at") or "")
    tags = _tags_html(item.get("verification_tags"))

    meta_parts = []
    if author:
        meta_parts.append(f"<span>作者 {author}</span>")
    if published:
        meta_parts.append(f"<span>发布 {published}</span>")
    if verified:
        meta_parts.append(f"<span>核查 {verified}</span>")
    if tags:
        meta_parts.append(tags)
    meta_html = f'<div class="item-meta">{"".join(meta_parts)}</div>' if meta_parts else ""

    summary_html = f'<div class="item-summary">{summary}</div>' if summary else ""
    notes_html = f'<div class="item-notes">备注：{notes}</div>' if notes else ""

    deal_html = ""
    deal = item.get("deal") if channel == "deals" else None
    if deal:
        rows = []
        if deal.get("threshold"):
            rows.append(f"<div>门槛：{escape_text(deal['threshold'])}</div>")
        if deal.get("deadline"):
            rows.append(f"<div>截止：{escape_text(deal['deadline'])}</div>")
        if deal.get("regions"):
            regions = "、".join(escape_text(r) for r in deal["regions"])
            rows.append(f"<div>地区：{regions}</div>")
        if deal.get("restrictions"):
            rows.append(f"<div>限制：{escape_text(deal['restrictions'])}</div>")
        if rows:
            deal_html = f'<div class="deal-box">{"".join(rows)}</div>'

    link_html = ""
    raw_url = item.get("source_url")
    try:
        safe_url = validate_url(raw_url) if raw_url else None
    except Exception:
        safe_url = None
    if safe_url:
        link_html = (
            f'<a class="item-link" href="{escape_text(safe_url)}" '
            f'rel="noopener noreferrer" target="_blank">阅读原文 →</a>'
        )

    return f"""
<article class="item">
  <h3 class="item-title">{title}</h3>
  {meta_html}
  {summary_html}
  {deal_html}
  {notes_html}
  {link_html}
</article>
""".strip()


def render_channel_section(channel: str, items: list[dict[str, Any]]) -> str:
    title = CHANNEL_TITLES.get(channel, channel)
    if not items:
        body = '<p class="empty">本期暂无条目</p>'
    else:
        body = "\n".join(render_item(i, channel) for i in items)
    return f"""
<section class="section" id="{escape_text(channel)}">
  <div class="section-header">
    <span class="section-title">{escape_text(title)}</span>
    <span class="section-count">{len(items)} 条</span>
  </div>
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
    css_href: str = "../assets/site.css",
    home_href: str = "../index.html",
) -> str:
    nav = {
        "home": ("首页", home_href),
        "daily": ("历史日报", f"{home_href}#timeline" if home_href.endswith("index.html") else "../index.html#timeline"),
        "builder": ("Builder", "../builder/index.html" if not css_href.startswith("assets/") else "builder/index.html"),
        "deals": ("羊毛雷达", "../deals/index.html" if not css_href.startswith("assets/") else "deals/index.html"),
        "editions": ("统一期次", "../e/index.html" if not css_href.startswith("assets/") else "e/index.html"),
    }
    # Fix relative nav when rendering root index-like pages with assets/site.css
    if css_href.startswith("assets/"):
        nav = {
            "home": ("首页", "index.html"),
            "daily": ("历史日报", "index.html#timeline"),
            "builder": ("Builder", "builder/index.html"),
            "deals": ("羊毛雷达", "deals/index.html"),
            "editions": ("统一期次", "e/index.html"),
        }

    links = []
    for key, (label, href) in nav.items():
        cls = "active" if key == active_nav else ""
        links.append(f'<a class="{cls}" href="{href}">{escape_text(label)}</a>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_text(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<header class="topnav">
  <a class="brand" href="{nav['home'][1]}">AI HOT</a>
  <nav class="nav-links">
    {''.join(links)}
  </nav>
</header>
<main class="page">
  <div class="page-kicker">{escape_text(kicker)}</div>
  <h1>{escape_text(heading)}</h1>
  <p class="page-lead">{escape_text(lead)}</p>
  {body}
</main>
<footer class="footer">
  <p>静态托管于 GitHub Pages · 数据经本地 JSON 摄取构建 · 不包含任何 webhook 密钥</p>
</footer>
</body>
</html>
"""
