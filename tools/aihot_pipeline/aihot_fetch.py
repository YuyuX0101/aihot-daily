"""AIHOT source fetch interfaces.

Supported live path: public HTTP API on aihot.news (see aihot_http.py).
Legacy HP/box used headed Chrome+CDP against the homepage; that adapter is
**not** implemented here and must not be presented as runnable.

Offline / parent-provided path: FileGroupsFetcher (groups JSON from external capture).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from .aihot_http import (
    DEFAULT_BASE,
    HttpFetchEvidence,
    fetch_daily_report,
    report_to_raw_items,
)


class DependencyGapError(RuntimeError):
    """Raised when a required upstream source is missing or disabled."""


class AihotFetcher(ABC):
    @abstractmethod
    def fetch_groups(self) -> list[dict[str, Any]]:
        """Return homepage day-groups (HP extract_items_from_page shape)."""

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
    """Load pre-captured groups JSON (offline / parent external upstream).

    Expected shape: ``{"groups":[{"day":"11月22日","rows":[...]}, ...]}``
    or a bare list of groups. Parent may produce this via headed browser
    computerUse on https://aihot.news/ when HTTP API is unavailable.
    """

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


class HttpDailyFetcher:
    """Fetch official structured daily via public REST API (not groups/CDP)."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("AIHOT_URL") or DEFAULT_BASE).rstrip("/")
        if self.base_url.rstrip("/").endswith("aihot.virxact.com"):
            # Old host now redirects; prefer documented public API host.
            self.base_url = DEFAULT_BASE
        self.last_evidence: HttpFetchEvidence | None = None
        self.last_report: dict[str, Any] | None = None

    def fetch_report(self, daily_date: date | str | None = None) -> dict[str, Any]:
        report, evidence = fetch_daily_report(daily_date, base_url=self.base_url)
        self.last_evidence = evidence
        self.last_report = report
        return report

    def fetch_items(self, daily_date: date | str | None = None) -> list[dict[str, Any]]:
        return report_to_raw_items(self.fetch_report(daily_date))

    def evidence_dict(self) -> dict[str, Any] | None:
        if self.last_evidence is None:
            return None
        return asdict(self.last_evidence)


def build_fetcher_from_env(
    *,
    groups_file: str | Path | None = None,
    mock_groups: list[dict[str, Any]] | None = None,
    prefer_http: bool | None = None,
) -> AihotFetcher | HttpDailyFetcher:
    """Resolve source. HTTP API preferred for live; groups-file for offline/parent capture.

    There is no CDP fetcher. Setting AIHOT_ALLOW_LIVE_FETCH alone enables HTTP.
    """
    if mock_groups is not None:
        return MockFetcher(mock_groups)
    path = groups_file or os.environ.get("AIHOT_GROUPS_FILE")
    if path:
        return FileGroupsFetcher(path)
    if prefer_http is None:
        prefer_http = (
            os.environ.get("AIHOT_HTTP_FETCH", "").strip() == "1"
            or os.environ.get("AIHOT_ALLOW_LIVE_FETCH", "").strip() == "1"
        )
    if prefer_http:
        return HttpDailyFetcher()
    raise DependencyGapError(
        "no AIHOT source configured: pass --http-aihot (public REST), "
        "--groups-file PATH (parent-captured groups JSON), or --skip-aihot. "
        "CDP browser adapter is not implemented and will not be invoked."
    )
