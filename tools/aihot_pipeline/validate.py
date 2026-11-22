"""Lightweight schema validation without external dependencies."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import SCHEMA_PATH
from .sanitize import SanitizationError, scrub_item_strings

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.:/@-]+$")
TAG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
CHANNELS = {"daily", "builder", "deals"}

ALLOWED_TAGS = {
    "page_reachable",
    "author_claim",
    "untested",
    "repo_reachable",
    "hearsay",
    "no_playable",
}

# Over-claim tags that imply实测/审计 — never allowed in feeds.
FORBIDDEN_TAGS = {"verified", "tested", "played", "audited"}


class ValidationError(ValueError):
    pass


def _require(obj: dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise ValidationError(f"missing required field: {key}")
    return obj[key]


def _load_schema_hints() -> dict[str, Any]:
    if SCHEMA_PATH.exists():
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {}


def validate_feed(doc: Any, *, allow_demo: bool = False) -> dict[str, Any]:
    """Validate a feed document; returns a normalized copy.

    Production ingest must call with allow_demo=False (default).
    tests/examples may set demo=true and pass allow_demo=True.
    """
    if not isinstance(doc, dict):
        raise ValidationError("feed must be a JSON object")

    allowed_top = {
        "schema_version",
        "edition_date",
        "channel",
        "source",
        "generated_at",
        "items",
        "demo",
        "channel_meta",
    }
    unknown = set(doc) - allowed_top
    if unknown:
        raise ValidationError(f"unknown top-level fields: {sorted(unknown)}")

    is_demo = doc.get("demo") is True
    if is_demo and not allow_demo:
        raise ValidationError("demo=true feeds are only allowed under tests/examples (allow_demo)")

    schema_version = _require(doc, "schema_version")
    if schema_version != "1.0":
        raise ValidationError("schema_version must be '1.0'")

    edition_date = _require(doc, "edition_date")
    if not isinstance(edition_date, str) or not DATE_RE.match(edition_date):
        raise ValidationError("edition_date must be YYYY-MM-DD")
    try:
        datetime.strptime(edition_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError(f"edition_date invalid: {exc}") from exc

    channel = _require(doc, "channel")
    if channel not in CHANNELS:
        raise ValidationError(f"channel must be one of {sorted(CHANNELS)}")

    source = _require(doc, "source")
    if not isinstance(source, str) or not (1 <= len(source) <= 64):
        raise ValidationError("source must be a non-empty string ≤64 chars")

    generated_at = _require(doc, "generated_at")
    if not isinstance(generated_at, str) or not (8 <= len(generated_at) <= 40):
        raise ValidationError("generated_at must be an ISO-ish string")

    items = _require(doc, "items")
    if not isinstance(items, list):
        raise ValidationError("items must be an array")
    if len(items) > 500:
        raise ValidationError("items exceeds max 500")

    normalized_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(items):
        try:
            item = _validate_item(raw, channel)
        except (ValidationError, SanitizationError) as exc:
            raise ValidationError(f"items[{idx}]: {exc}") from exc
        if item["id"] in seen_ids:
            raise ValidationError(f"items[{idx}]: duplicate id within feed: {item['id']}")
        seen_ids.add(item["id"])
        normalized_items.append(item)

    channel_meta = doc.get("channel_meta")
    if channel_meta is not None and not isinstance(channel_meta, dict):
        raise ValidationError("channel_meta must be an object")

    _load_schema_hints()

    out: dict[str, Any] = {
        "schema_version": "1.0",
        "edition_date": edition_date,
        "channel": channel,
        "source": source,
        "generated_at": generated_at,
        "items": normalized_items,
    }
    if is_demo:
        out["demo"] = True
    if channel_meta:
        out["channel_meta"] = channel_meta
    return out


def _validate_item(raw: Any, channel: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError("item must be an object")

    allowed = {
        "id",
        "title",
        "summary",
        "source_url",
        "playable_url",
        "repo_url",
        "author",
        "published_at",
        "verified_at",
        "verification_tags",
        "author_claim",
        "verified_evidence",
        "notes",
        "score",
        "deal",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValidationError(f"unknown item fields: {sorted(unknown)}")

    item_id = raw.get("id")
    if not isinstance(item_id, str) or not ID_RE.match(item_id):
        raise ValidationError("id must match [A-Za-z0-9_.:/@-]+")
    title = raw.get("title")
    if not isinstance(title, str) or not (1 <= len(title) <= 200):
        raise ValidationError("title required (1–200 chars)")

    for key, maxlen in (
        ("summary", 2000),
        ("author", 120),
        ("notes", 500),
        ("published_at", 40),
        ("verified_at", 40),
        ("author_claim", 2000),
        ("verified_evidence", 2000),
    ):
        val = raw.get(key)
        if val is None:
            continue
        if not isinstance(val, str) or len(val) > maxlen:
            raise ValidationError(f"{key} must be string ≤{maxlen}")

    tags = raw.get("verification_tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 20:
            raise ValidationError("verification_tags must be list ≤20")
        for t in tags:
            if not isinstance(t, str) or not TAG_RE.match(t):
                raise ValidationError("invalid verification tag")
            if t in FORBIDDEN_TAGS:
                raise ValidationError(
                    f"tag '{t}' forbidden (over-claims实测); "
                    "use page_reachable / author_claim / untested / repo_reachable"
                )
            if t not in ALLOWED_TAGS:
                raise ValidationError(f"unknown verification tag '{t}'")

    score = raw.get("score")
    if score is not None and (not isinstance(score, int) or score < 0 or score > 100000):
        raise ValidationError("score must be int 0–100000")

    deal = raw.get("deal")
    if deal is not None:
        if channel != "deals":
            raise ValidationError("deal object only allowed on deals channel")
        if not isinstance(deal, dict):
            raise ValidationError("deal must be object")
        deal_allowed = {"threshold", "deadline", "regions", "restrictions"}
        if set(deal) - deal_allowed:
            raise ValidationError(f"unknown deal fields: {sorted(set(deal) - deal_allowed)}")
        for key, maxlen in (("threshold", 200), ("deadline", 40), ("restrictions", 300)):
            val = deal.get(key)
            if val is None:
                continue
            if not isinstance(val, str) or len(val) > maxlen:
                raise ValidationError(f"deal.{key} invalid")
        regions = deal.get("regions")
        if regions is not None:
            if not isinstance(regions, list) or len(regions) > 30:
                raise ValidationError("deal.regions invalid")
            for r in regions:
                if not isinstance(r, str) or not TAG_RE.match(r):
                    raise ValidationError("deal.regions entry invalid")

    return scrub_item_strings(raw)


def load_and_validate_file(path: Path, *, allow_demo: bool = False) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    return validate_feed(doc, allow_demo=allow_demo)
