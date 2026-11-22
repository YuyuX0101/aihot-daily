"""Field sanitization and injection guards for external feed content."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

# Patterns that indicate script/event injection attempts in plain-text fields.
_DANGEROUS_TEXT = re.compile(
    r"(?is)(<\s*script\b|</\s*script\b|javascript\s*:|vbscript\s*:|data\s*:text/html|"
    r"\bon(?:error|load|click|mouseover|focus|submit)\s*=)"
)

_ALLOWED_SCHEMES = {"http", "https"}


class SanitizationError(ValueError):
    """Raised when an external field fails security validation."""


def reject_dangerous_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise SanitizationError(f"{field}: must be a string")
    if _DANGEROUS_TEXT.search(value):
        raise SanitizationError(f"{field}: rejected potentially injectable content")
    return value


def escape_text(value: Any) -> str:
    """HTML-escape for safe insertion into text nodes / attributes."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def validate_url(url: str | None, field: str = "source_url") -> str | None:
    if url is None or url == "":
        return None
    if not isinstance(url, str):
        raise SanitizationError(f"{field}: must be a string")
    reject_dangerous_text(url, field)
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SanitizationError(f"{field}: only http/https URLs are allowed")
    if not parsed.netloc:
        raise SanitizationError(f"{field}: missing host")
    return url.strip()


def scrub_item_strings(item: dict[str, Any]) -> dict[str, Any]:
    """Validate string fields for injection; return a shallow-copied item."""
    out = dict(item)
    for key in ("id", "title", "summary", "author", "notes", "published_at", "verified_at"):
        if key in out and out[key] is not None:
            out[key] = reject_dangerous_text(str(out[key]), key)
    if "source_url" in out:
        out["source_url"] = validate_url(out.get("source_url"))
    tags = out.get("verification_tags")
    if tags is not None:
        if not isinstance(tags, list):
            raise SanitizationError("verification_tags: must be a list")
        cleaned = []
        for t in tags:
            cleaned.append(reject_dangerous_text(str(t), "verification_tags[]"))
        out["verification_tags"] = cleaned
    deal = out.get("deal")
    if deal is not None:
        if not isinstance(deal, dict):
            raise SanitizationError("deal: must be an object")
        deal_out = dict(deal)
        for key in ("threshold", "deadline", "restrictions"):
            if key in deal_out and deal_out[key] is not None:
                deal_out[key] = reject_dangerous_text(str(deal_out[key]), f"deal.{key}")
        regions = deal_out.get("regions")
        if regions is not None:
            if not isinstance(regions, list):
                raise SanitizationError("deal.regions: must be a list")
            deal_out["regions"] = [
                reject_dangerous_text(str(r), "deal.regions[]") for r in regions
            ]
        out["deal"] = deal_out
    return out
