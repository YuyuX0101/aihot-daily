"""HTML rendering helpers — editorial shell; all dynamic text escaped; Beijing time."""

from __future__ import annotations

from typing import Any

from .sanitize import escape_text, validate_url
from .timefmt import format_beijing

CHANNEL_TITLES = {
    "daily": "AI HOT 日报",
    "builder": "Builder 一手作品速报",
    "deals": "AI 羊毛雷达",
}

TAG_LABELS = {
    "page_reachable": "页面可达",
    "author_claim": "作者声明",
    "untested": "未实测",
    "repo_reachable": "仓库可达",
    "hearsay": "二手转述",
    "no_playable": "无可玩页",
    "aihot_repost": "AIHOT转载",
    "unverified_upstream": "未独立核验",
}

WARN_TAGS = {
    "untested",
    "hearsay",
    "author_claim",
    "no_playable",
    "aihot_repost",
    "unverified_upstream",
}

DEFAULT_EMPTY = {
    "daily": "当日暂无 AI HOT 日报生成结果；请查看最近历史日报，勿将示例内容当作当日资讯。",
    "builder": "本期暂无 Builder 条目。",
    "deals": "本期暂无羊毛条目。",
}


def _tags_html(tags: list[str] | None) -> str:
    if not tags:
        return ""
    bits = []
    for t in tags:
        label = TAG_LABELS.get(t, t)
        cls = "tag warn" if t in WARN_TAGS else "tag"
        bits.append(f'<span class="{cls}">{escape_text(label)}</span>')
    return " ".join(bits)


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
        f'rel="noopener noreferrer" target="_blank">{escape_text(label)} →</a>'
    )


def render_item(item: dict[str, Any], channel: str) -> str:
    title = escape_text(item.get("title"))
    author = escape_text(item.get("author") or "")
    notes = escape_text(item.get("notes") or "")
    published = format_beijing(item.get("published_at") or "")
    verified = format_beijing(item.get("verified_at") or "")
    tags = _tags_html(item.get("verification_tags"))
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
    if tags:
        meta_parts.append(tags)
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
    link_html = f'<div class="item-links">{" · ".join(links)}</div>' if links else ""

    return f"""
<article class="item">
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
        collapsed_attr = ' data-collapsed="true" class="section is-empty"'
    else:
        body = "\n".join(render_item(i, channel) for i in items)
        collapsed_attr = ' class="section"'

    return f"""
<section{collapsed_attr} id="{escape_text(channel)}">
  <div class="section-header">
    <span class="section-title">{escape_text(title)}</span>
    <span class="section-count">{count} 条{" · 已折叠" if empty else ""}</span>
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
            "daily": ("历史日报", "index.html#timeline"),
            "builder": ("Builder", "builder/index.html"),
            "deals": ("羊毛雷达", "deals/index.html"),
            "editions": ("统一期次", "e/index.html"),
        }
    else:
        nav = {
            "home": ("首页", home_href),
            "daily": ("历史日报", "../index.html#timeline"),
            "builder": ("Builder", "../builder/index.html"),
            "deals": ("羊毛雷达", "../deals/index.html"),
            "editions": ("统一期次", "../e/index.html"),
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

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_text(title)}</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<a class="skip-link" href="#main">跳到正文</a>
<header class="site-header">
  <div class="site-header-inner">
    <a class="brand" href="{nav['home'][1]}">AI <span>HOT</span></a>
    <nav class="nav-links" aria-label="主导航">
      {''.join(links)}
    </nav>
  </div>
</header>
{banner}
<main class="page" id="main">
  <div class="kicker">{escape_text(kicker)}</div>
  <h1>{escape_text(heading)}</h1>
  <p class="page-lead">{escape_text(lead)}</p>
  {body}
</main>
<footer class="site-footer">
  <p>静态托管于 GitHub Pages · 数据经本地 JSON 摄取构建 · 不含 webhook 密钥</p>
  <p>展示时间为北京时间（Asia/Shanghai）· 页可打开≠功能/隐私审计 · 未实测不等于不可用</p>
</footer>
</body>
</html>
"""
