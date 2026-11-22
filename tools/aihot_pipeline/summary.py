"""Unified Feishu summary text (preview / dry-run payload).

Daily (AIHOT) section: count + honesty line only — do not amplify unverified
breakthrough/security headlines as settled facts. Builder keeps title highlights
with its own verification boundary. Deals keeps empty-state honesty.
"""

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
    date = edition.get("edition_date", "")
    channels = edition.get("channels") or {}
    lines: list[str] = [f"AIHOT 统一速报 · {date}", ""]

    totals = []
    for key in ("daily", "builder", "deals"):
        bucket = channels.get(key) or {}
        items = bucket.get("items") or []
        meta = bucket.get("meta") or {}
        label = CHANNEL_LABELS[key]
        totals.append(f"{label} {len(items)} 条")

        if key == "daily":
            lines.append(f"【{label}】")
            if items:
                lines.append(f"· {len(items)} 条（上游汇总，未独立核验）")
                lines.append("· 重大科学/安全等断言请点进站点查阅原文，勿当作本站已证实事实")
            elif meta.get("empty_message"):
                lines.append(f"· {meta['empty_message']}")
            else:
                lines.append("· 0 条")
            lines.append("")
            continue

        tops = _top_titles(items, 3)
        if tops:
            lines.append(f"【{label}】")
            for t in tops:
                lines.append(f"· {t}")
            lines.append("")
        elif meta.get("empty_message"):
            lines.append(f"【{label}】")
            lines.append(f"· {meta['empty_message']}")
            lines.append("")

    lines.append("汇总：" + " / ".join(totals))
    edition_url = f"{site_base.rstrip('/')}/e/{date}.html"
    lines.append(f"完整内容：{edition_url}")
    lines.append(f"站点首页：{site_base.rstrip('/')}/")
    return "\n".join(lines).strip() + "\n"
