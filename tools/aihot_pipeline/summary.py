"""Unified Feishu summary text (preview / dry-run payload)."""

from __future__ import annotations

from typing import Any

from .paths import SITE_BASE_URL


CHANNEL_LABELS = {
    "daily": "AI HOT 日报",
    "builder": "Builder 一手作品",
    "deals": "AI 羊毛雷达",
}


def _top_titles(items: list[dict[str, Any]], n: int = 3) -> list[str]:
    ranked = sorted(items, key=lambda x: (-int(x.get("score") or 0), x.get("id", "")))
    return [i.get("title", "").strip() for i in ranked[:n] if i.get("title")]


def build_summary_text(edition: dict[str, Any], site_base: str = SITE_BASE_URL) -> str:
    """Compose a short Feishu-friendly summary + site link.

    Intentionally NOT a full dump — website holds the full results.
    """
    date = edition.get("edition_date", "")
    channels = edition.get("channels") or {}
    lines: list[str] = [f"AIHOT 统一速报 · {date}", ""]

    totals = []
    for key in ("daily", "builder", "deals"):
        bucket = channels.get(key) or {}
        items = bucket.get("items") or []
        label = CHANNEL_LABELS[key]
        totals.append(f"{label} {len(items)} 条")
        tops = _top_titles(items, 3)
        if tops:
            lines.append(f"【{label}】")
            for t in tops:
                lines.append(f"· {t}")
            lines.append("")

    lines.append("汇总：" + " / ".join(totals))
    edition_url = f"{site_base.rstrip('/')}/e/{date}.html"
    lines.append(f"完整内容：{edition_url}")
    lines.append(f"站点首页：{site_base.rstrip('/')}/")
    return "\n".join(lines).strip() + "\n"
