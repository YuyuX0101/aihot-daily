"""Unified offline-first runner: AIHOT daily + builder/deals feeds → one edition + one notify.

Defaults:
  - dry_run for Feishu + git push
  - does NOT call legacy generator send_feishu / git push
  - uses Mock/File fetcher unless live CDP explicitly allowed (still may DependencyGap)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .aihot_fetch import AihotFetcher, DependencyGapError, FileGroupsFetcher, MockFetcher
from .aihot_logic import SCORE_THRESHOLD, default_target_date, filter_target_items, shanghai_today
from .build import build_site
from .convert_aihot import items_to_daily_feed
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
    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    state_path: Path | None = None
    force_notify: bool = False
    skip_aihot_fetch: bool = False
    empty_deals_message: str = (
        "本次未找到同时满足最近12小时新鲜度与可核验要求的新优惠（不等于全网无优惠）。"
    )
    empty_daily_message: str = (
        "当日暂无 AI HOT 日报生成结果；下方提供最近历史日报链接，未插入示例资讯。"
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


def _fetcher(cfg: RunConfig) -> AihotFetcher:
    if cfg.mock_groups is not None:
        return MockFetcher(cfg.mock_groups)
    if cfg.aihot_groups_file:
        return FileGroupsFetcher(cfg.aihot_groups_file)
    raise DependencyGapError(
        "unified runner offline mode requires mock_groups or aihot_groups_file "
        "(live CDP not assumed available)"
    )


def run_unified(cfg: RunConfig) -> RunResult:
    target = cfg.edition_date or default_target_date()
    date_str = target.strftime("%Y-%m-%d")
    stages: dict[str, Any] = {
        "beijing_today": shanghai_today().isoformat(),
        "edition_date": date_str,
        "dry_run": cfg.dry_run,
        "score_threshold": cfg.score_threshold,
    }

    try:
        # --- AIHOT source ---
        aihot_items: list[dict[str, Any]] = []
        if not cfg.skip_aihot_fetch:
            fetcher = _fetcher(cfg)
            groups = fetcher.fetch_groups()
            stages["aihot_groups"] = len(groups)
            aihot_items = filter_target_items(
                groups, target, score_threshold=cfg.score_threshold, today=shanghai_today()
            )
            aihot_items = fetcher.enrich_summaries(aihot_items)
            stages["aihot_items"] = len(aihot_items)

            daily_feed = items_to_daily_feed(aihot_items, edition_date=target)
            apply_feed(daily_feed)
            stages["daily_ingest"] = {"count": len(daily_feed["items"])}

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
            # Explicit zero-deal meta when caller intends deals channel present
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
        # In dry-run acceptance tests we may mark published=True to exercise notify mock
        # without real push — only when explicitly requested via cfg.published for mock path.
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

        # Single unified notify — never call legacy Top5 send_feishu
        notify_result = notify_edition(
            date_str,
            dry_run=cfg.dry_run,
            require_published=cfg.require_publish_for_notify,
            published=notify_published if cfg.require_publish_for_notify else True,
            force=cfg.force_notify,
            sender=mock_sender if (not cfg.dry_run and cfg.published) else None,
            state_path=cfg.state_path,
        )
        # Also expose gated send_text preview for operator tooling
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
        return RunResult(
            ok=False,
            edition_date=date_str,
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
