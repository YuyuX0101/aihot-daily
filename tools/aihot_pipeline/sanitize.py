"""Field sanitization and injection guards for external feed content."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

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
    out = dict(item)
    for key in (
        "id",
        "title",
        "summary",
        "author",
        "notes",
        "published_at",
        "verified_at",
        "author_claim",
        "verified_evidence",
    ):
        if key in out and out[key] is not None:
            out[key] = reject_dangerous_text(str(out[key]), key)
    for key in ("source_url", "playable_url", "repo_url"):
        if key in out:
            out[key] = validate_url(out.get(key), field=key)
    tags = out.get("verification_tags")
    if tags is not None:
        if not isinstance(tags, list):
            raise SanitizationError("verification_tags: must be a list")
        out["verification_tags"] = [
            reject_dangerous_text(str(t), "verification_tags[]") for t in tags
        ]
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
