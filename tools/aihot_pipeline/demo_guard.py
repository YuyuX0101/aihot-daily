"""Prevent demo/example feeds from entering production editions or site output."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

DEMO_HOST_SUFFIXES = (
    "example.com",
    "example.org",
    "example.net",
    "test",
)

# Tags that over-claim real-world testing and must not appear alone as "已实测".
FORBIDDEN_OVERCLAIM_TAGS = {"verified", "tested", "played", "audited"}


class DemoGuardError(ValueError):
    pass


def _host_is_demo(url: str | None) -> bool:
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host in {"localhost", "127.0.0.1"}:
        return True
    return any(host == s or host.endswith("." + s) for s in DEMO_HOST_SUFFIXES)


def assert_production_feed(feed: dict[str, Any]) -> None:
    """Raise if a feed is marked demo or uses example hosts."""
    if feed.get("demo") is True:
        raise DemoGuardError("demo feeds are not allowed in production ingest")
    source = str(feed.get("source") or "")
    if source.startswith("demo") or "example" in source.lower():
        raise DemoGuardError(f"demo/example source not allowed in production: {source}")
    for idx, item in enumerate(feed.get("items") or []):
        for key in ("source_url", "playable_url", "repo_url"):
            url = item.get(key)
            if _host_is_demo(url):
                raise DemoGuardError(
                    f"items[{idx}].{key} uses demo host; keep demos under tests/examples only"
                )
        tags = set(item.get("verification_tags") or [])
        # Bare over-claim without the required honesty tags is rejected.
        if tags & FORBIDDEN_OVERCLAIM_TAGS:
            if "untested" not in tags:
                raise DemoGuardError(
                    f"items[{idx}]: tag {sorted(tags & FORBIDDEN_OVERCLAIM_TAGS)} "
                    "implies实测; use page_reachable/author_claim/untested instead"
                )
            # Even with untested, ban the overclaim synonym to avoid UX confusion.
            raise DemoGuardError(
                f"items[{idx}]: forbidden overclaim tag {sorted(tags & FORBIDDEN_OVERCLAIM_TAGS)}; "
                "use page_reachable / author_claim / untested / repo_reachable"
            )


def assert_edition_has_no_demo_urls(edition: dict[str, Any]) -> None:
    for channel, bucket in (edition.get("channels") or {}).items():
        for idx, item in enumerate((bucket or {}).get("items") or []):
            for key in ("source_url", "playable_url", "repo_url"):
                if _host_is_demo(item.get(key)):
                    raise DemoGuardError(
                        f"edition {edition.get('edition_date')} {channel}[{idx}] "
                        f"contains demo URL in {key}"
                    )
