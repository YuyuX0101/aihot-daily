"""AIHOT source fetch interfaces.

Live CDP fetch depends on a headed Chrome/Chromium instance (box inventory notes
headless fails to extract aihot data). This cloud VM may have Chrome, but we do
**not** claim the full CDP scrape path is production-ready here.

Default path for tests / offline: MockFetcher or FileGroupsFetcher.
Live CDP is behind AIHOT_ALLOW_LIVE_FETCH=1 and still may fail with DependencyGap.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DependencyGapError(RuntimeError):
    """Raised when a live dependency (Chrome/CDP/display) is missing or disabled."""


class AihotFetcher(ABC):
    @abstractmethod
    def fetch_groups(self) -> list[dict[str, Any]]:
        """Return homepage day-groups as produced by extract_items_from_page JS."""

    def enrich_summaries(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optional detail-page enrichment. Default: leave items unchanged."""
        return items


class MockFetcher(AihotFetcher):
    def __init__(self, groups: list[dict[str, Any]]):
        self.groups = groups

    def fetch_groups(self) -> list[dict[str, Any]]:
        return list(self.groups)

    def enrich_summaries(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for item in items:
            copy = dict(item)
            if not copy.get("summary"):
                reason = copy.get("reason") or ""
                copy["summary"] = reason if len(reason) > 20 else copy.get("title", "")
            out.append(copy)
        return out


class FileGroupsFetcher(AihotFetcher):
    """Load pre-captured groups JSON (offline / CI)."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def fetch_groups(self) -> list[dict[str, Any]]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "groups" in data:
            return list(data["groups"])
        if isinstance(data, list):
            return data
        raise ValueError(f"unexpected groups file shape: {self.path}")

    def enrich_summaries(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return MockFetcher([]).enrich_summaries(items)


class CdpFetcher(AihotFetcher):
    """Optional live fetcher. Not used by default tests.

    Requires:
      - AIHOT_ALLOW_LIVE_FETCH=1
      - Chrome/Chromium binary (AIHOT_CHROME_BIN)
      - Prefer headed mode + DISPLAY (inventory: headless fails on aihot)
    """

    def __init__(self, aihot_url: str | None = None):
        self.aihot_url = aihot_url or os.environ.get(
            "AIHOT_URL", "https://aihot.virxact.com/"
        )

    def _ensure_allowed(self) -> None:
        if os.environ.get("AIHOT_ALLOW_LIVE_FETCH", "").strip() != "1":
            raise DependencyGapError(
                "live CDP fetch disabled (set AIHOT_ALLOW_LIVE_FETCH=1 to attempt). "
                "Cloud environment Chrome/DISPLAY readiness is NOT assumed."
            )

    def fetch_groups(self) -> list[dict[str, Any]]:
        self._ensure_allowed()
        # Import inventory CDP helpers lazily so offline imports never start Chrome.
        try:
            from vendor.box_inventory_bridge import extract_groups_via_cdp
        except Exception as exc:  # pragma: no cover - import path messaging
            raise DependencyGapError(
                f"CDP bridge unavailable: {exc}. "
                "Use FileGroupsFetcher/MockFetcher for offline runs."
            ) from exc
        return extract_groups_via_cdp(self.aihot_url)

    def enrich_summaries(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._ensure_allowed()
        try:
            from vendor.box_inventory_bridge import enrich_via_cdp
        except Exception as exc:  # pragma: no cover
            raise DependencyGapError(f"CDP enrich unavailable: {exc}") from exc
        return enrich_via_cdp(items)


def build_fetcher_from_env(
    *,
    groups_file: str | Path | None = None,
    mock_groups: list[dict[str, Any]] | None = None,
) -> AihotFetcher:
    if mock_groups is not None:
        return MockFetcher(mock_groups)
    path = groups_file or os.environ.get("AIHOT_GROUPS_FILE")
    if path:
        return FileGroupsFetcher(path)
    if os.environ.get("AIHOT_ALLOW_LIVE_FETCH", "").strip() == "1":
        return CdpFetcher()
    raise DependencyGapError(
        "no fetcher configured: provide AIHOT_GROUPS_FILE / mock groups, "
        "or set AIHOT_ALLOW_LIVE_FETCH=1 (Chrome/CDP dependency gap may still apply)"
    )
