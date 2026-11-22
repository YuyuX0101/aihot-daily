"""Display-time helpers: always Asia/Shanghai, never bare trailing Z."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def to_shanghai(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI)


def parse_instant(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Already a Shanghai wall-clock like "2026-11-21 23:23"
    if "T" not in text and "+" not in text and not text.endswith("Z"):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                naive = datetime.strptime(text, fmt)
                return naive.replace(tzinfo=SHANGHAI)
            except ValueError:
                continue
        return None
    iso = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def format_beijing(value: str | None) -> str:
    """Convert ISO/Z/local strings to 'YYYY-MM-DD HH:MM 北京时间'."""
    if value is None or value == "":
        return ""
    dt = parse_instant(value)
    if dt is None:
        # Fail closed on display: never echo raw trailing Z to users.
        cleaned = value.strip().rstrip("Z").rstrip("z")
        return cleaned
    local = to_shanghai(dt)
    return local.strftime("%Y-%m-%d %H:%M") + " 北京时间"
