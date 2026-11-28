"""Unified offline-first runner: AIHOT daily + builder/deals feeds → one edition + one notify.

Defaults:
  - dry_run for Feishu + git push
  - does NOT call legacy generator send_feishu / git push
  - AIHOT source: public HTTP API (--http-aihot) or groups-file; no CDP adapter
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .aihot_fetch import (
    DependencyGapError,
    FileGroupsFetcher,
    HttpDailyFetcher,
    MockFetcher,
)
from .aihot_http import resolve_daily_date
from .aihot_logic import SCORE_THRESHOLD, filter_target_items, shanghai_today
from .build import build_site
from .convert_aihot import items_to_daily_feed, official_report_to_daily_feed
from .daily_html import write_daily_html
from .feishu_gate import send_text
from .ingest import apply_feed, ensure_channel_meta, load_edition, refresh_editions_index
from .notify import mock_sender, notify_edition
from .paths import REPO_ROOT
from .publish_gate import publish_repo
from .summary import build_summary_text
from .validate import validate_feed

log = logging.getLogger("aihot.unified_runner")


@dataclass
class RunConfig:
    edition_date: date | None = None
    dry_run: bool = True
    write_legacy_daily_html: bool = True
    require_publish_for_notify: bool = True
    published: bool = False  # set True only after successful real publish
    score_threshold: int = SCORE_THRESHOLD
    builder_feed: Path | None = None
    deals_feed: Path | None = None
    aihot_groups_file: Path | None = None
    mock_groups: list[dict[str, Any]] | None = None
    use_http_aihot: bool = False
    aihot_base_url: str | None = None
    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    state_path: Path | None = None
    force_notify: bool = False
    skip_aihot_fetch: bool = False
    empty_deals_message: str = (
        "本次未找到同时满足最近12小时新鲜度与可核验要求的新优惠（不等于全网无优惠）。"
    )
    empty_daily_message: str = (
        "当日暂无 AI 动态生成结果；下方提供最近历史日报链接，未插入示例资讯。"
    )


@dataclass
class RunResult:
    ok: bool
    edition_date: str
    dry_run: bool
    stages: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    notify_preview: str | None = None


def _load_optional_feed(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return validate_feed(json.loads(path.read_text(encoding="utf-8")), allow_demo=False)


def run_unified(cfg: RunConfig) -> RunResult:
    stages: dict[str, Any] = {
        "beijing_today": shanghai_today().isoformat(),
        "dry_run": cfg.dry_run,
        "score_threshold": cfg.score_threshold,
    }

    try:
        # --- resolve edition date (official API latest unless CLI overrides) ---
        if cfg.skip_aihot_fetch and cfg.edition_date is None:
            raise ValueError("edition --date required when --skip-aihot (no API date probe)")

        resolved = None
        if cfg.use_http_aihot and not cfg.skip_aihot_fetch and not cfg.aihot_groups_file and cfg.mock_groups is None:
            resolved = resolve_daily_date(
                cfg.edition_date,
                base_url=cfg.aihot_base_url or "https://aihot.news",
                probe_latest=True,
            )
            target = resolved.edition_date
            stages["date_resolution"] = {
                "edition_date": target.isoformat(),
                "beijing_today": resolved.beijing_today.isoformat(),
                "hp_legacy_yesterday": resolved.hp_legacy_yesterday.isoformat(),
                "resolution": resolved.resolution,
                "latest_api_date": resolved.latest_api_date.isoformat()
                if resolved.latest_api_date
                else None,
                "note": resolved.note,
            }
        else:
            if cfg.edition_date is None:
                # Offline groups/mock path: keep HP default (yesterday) unless caller sets date.
                from .aihot_logic import default_target_date

                target = default_target_date()
                stages["date_resolution"] = {
                    "edition_date": target.isoformat(),
                    "beijing_today": shanghai_today().isoformat(),
                    "resolution": "hp_legacy_yesterday_default",
                    "note": (
                        "No HTTP probe; defaulting to HP legacy yesterday. "
                        "Pass --date to pin the official daily date."
                    ),
                }
            else:
                target = cfg.edition_date
                stages["date_resolution"] = {
                    "edition_date": target.isoformat(),
                    "beijing_today": shanghai_today().isoformat(),
                    "resolution": "cli",
                    "note": "Explicit --date without HTTP latest probe in this branch.",
                }

        date_str = target.strftime("%Y-%m-%d")
        stages["edition_date"] = date_str

        # --- AIHOT source ---
        aihot_items: list[dict[str, Any]] = []
        if not cfg.skip_aihot_fetch:
            if cfg.mock_groups is not None:
                fetcher = MockFetcher(cfg.mock_groups)
                groups = fetcher.fetch_groups()
                stages["aihot_mode"] = "mock_groups"
                stages["aihot_groups"] = len(groups)
                aihot_items = filter_target_items(
                    groups, target, score_threshold=cfg.score_threshold, today=shanghai_today()
                )
                aihot_items = fetcher.enrich_summaries(aihot_items)
                daily_feed = items_to_daily_feed(
                    aihot_items, edition_date=target, source="aihot-mock-groups"
                )
            elif cfg.aihot_groups_file:
                fetcher = FileGroupsFetcher(cfg.aihot_groups_file)
                groups = fetcher.fetch_groups()
                stages["aihot_mode"] = "groups_file"
                stages["aihot_groups_file"] = str(cfg.aihot_groups_file)
                stages["aihot_groups"] = len(groups)
                aihot_items = filter_target_items(
                    groups, target, score_threshold=cfg.score_threshold, today=shanghai_today()
                )
                aihot_items = fetcher.enrich_summaries(aihot_items)
                daily_feed = items_to_daily_feed(
                    aihot_items,
                    edition_date=target,
                    source="aihot-groups-file",
                    source_meta={
                        "groups_file": str(cfg.aihot_groups_file),
                        "note": "Parent/external capture; not live HTTP API.",
                    },
                )
            elif cfg.use_http_aihot:
                http = HttpDailyFetcher(cfg.aihot_base_url)
                report = http.fetch_report(target)
                if str(report.get("date")) != date_str:
                    raise ValueError(
                        f"API daily date {report.get('date')} != edition {date_str}"
                    )
                evidence = http.evidence_dict() or {}
                daily_feed = official_report_to_daily_feed(report, evidence=evidence)
                aihot_items = [
                    {
                        "title": it["title"],
                        "score": it.get("score") or 0,
                        "src": it.get("author") or "",
                        "link": it.get("source_url") or "",
                        "summary": it.get("summary") or "",
                        "reason": it.get("summary") or "",
                    }
                    for it in daily_feed["items"]
                ]
                stages["aihot_mode"] = "public_http_api"
                stages["aihot_http_evidence"] = evidence
                stages["aihot_official_page"] = (daily_feed.get("source_meta") or {}).get(
                    "official_page"
                )
            else:
                raise DependencyGapError(
                    "AIHOT source required: use --http-aihot (public REST /api/v1/dailies), "
                    "--groups-file PATH, or --skip-aihot. "
                    "CDP adapter is not implemented."
                )

            stages["aihot_items"] = len(daily_feed["items"])
            apply_feed(daily_feed)
            stages["daily_ingest"] = {
                "count": len(daily_feed["items"]),
                "source": daily_feed.get("source"),
                "aihot_daily_date": (daily_feed.get("source_meta") or {}).get(
                    "aihot_daily_date", date_str
                ),
            }

            if aihot_items and cfg.write_legacy_daily_html:
                html_path = write_daily_html(cfg.repo_root, target, aihot_items)
                stages["legacy_html"] = str(html_path)
            elif not aihot_items:
                ensure_channel_meta(
                    date_str,
                    "daily",
                    {
                        "empty_reason": "no_aihot_items_above_threshold",
                        "empty_message": cfg.empty_daily_message,
                    },
                )
        else:
            stages["aihot_skipped"] = True

        # --- builder / deals feeds (file import) ---
        builder = _load_optional_feed(cfg.builder_feed)
        if builder:
            if builder["edition_date"] != date_str:
                raise ValueError(
                    f"builder feed edition_date {builder['edition_date']} != runner {date_str}"
                )
            stages["builder_ingest"] = apply_feed(builder)

        deals = _load_optional_feed(cfg.deals_feed)
        if deals is not None:
            if deals["edition_date"] != date_str:
                raise ValueError(
                    f"deals feed edition_date {deals['edition_date']} != runner {date_str}"
                )
            stages["deals_ingest"] = apply_feed(deals)
            if len(deals.get("items") or []) == 0:
                ensure_channel_meta(
                    date_str,
                    "deals",
                    {
                        "empty_reason": "no_match_12h_verifiable",
                        "empty_message": deals.get("channel_meta", {}).get(
                            "empty_message", cfg.empty_deals_message
                        ),
                    },
                )
        else:
            ensure_channel_meta(
                date_str,
                "deals",
                {
                    "empty_reason": "no_match_12h_verifiable",
                    "empty_message": cfg.empty_deals_message,
                },
            )
            stages["deals_ingest"] = {"total": 0, "assumed_empty": True}

        refresh_editions_index()
        build_result = build_site()
        if not build_result.get("ok"):
            raise RuntimeError(f"build failed: {build_result.get('errors')}")
        stages["build"] = {
            "written": build_result.get("written"),
            "edition_dates": build_result.get("edition_dates"),
        }

        edition = load_edition(date_str)
        preview = build_summary_text(edition)
        stages["summary_preview"] = preview

        # Publish gate (default dry-run) — failure here must not notify
        pub = publish_repo(
            cfg.repo_root,
            message=f"update: {date_str} unified edition",
            dry_run=cfg.dry_run,
        )
        stages["publish"] = pub
        published_flag = bool(pub.get("published")) or (
            cfg.published and cfg.dry_run is False
        )
        notify_published = published_flag if not cfg.dry_run else cfg.published

        if not pub.get("ok"):
            stages["notify"] = {
                "skipped": True,
                "reason": "publish_failed_no_notify",
                "publish": pub,
            }
            return RunResult(
                ok=False,
                edition_date=date_str,
                dry_run=cfg.dry_run,
                stages=stages,
                error="publish_failed",
                notify_preview=preview,
            )

        notify_result = notify_edition(
            date_str,
            dry_run=cfg.dry_run,
            require_published=cfg.require_publish_for_notify,
            published=notify_published if cfg.require_publish_for_notify else True,
            force=cfg.force_notify,
            sender=mock_sender if (not cfg.dry_run and cfg.published) else None,
            state_path=cfg.state_path,
        )
        gate = send_text(preview, dry_run=True)
        stages["notify"] = notify_result
        stages["feishu_gate_preview"] = gate

        return RunResult(
            ok=True,
            edition_date=date_str,
            dry_run=cfg.dry_run,
            stages=stages,
            notify_preview=preview,
        )
    except Exception as exc:
        log.exception("unified run failed")
        stages["notify"] = {
            "skipped": True,
            "reason": "run_failed_no_notify",
            "error": str(exc),
        }
        # best-effort edition_date for error payload
        ed = stages.get("edition_date") or (
            cfg.edition_date.isoformat() if cfg.edition_date else shanghai_today().isoformat()
        )
        return RunResult(
            ok=False,
            edition_date=str(ed),
            dry_run=cfg.dry_run,
            stages=stages,
            error=str(exc),
        )


def run_result_to_dict(result: RunResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "edition_date": result.edition_date,
        "dry_run": result.dry_run,
        "error": result.error,
        "notify_preview": result.notify_preview,
        "stages": result.stages,
    }
