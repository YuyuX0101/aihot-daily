"""CLI entrypoints for ingest / build / notify / summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datetime import datetime

from .build import build_site
from .ingest import ingest_inbox, load_edition
from .notify import mock_sender, notify_edition
from .summary import build_summary_text
from .unified_runner import RunConfig, run_result_to_dict, run_unified


def _print_json(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_ingest(_: argparse.Namespace) -> int:
    result = ingest_inbox()
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_build(_: argparse.Namespace) -> int:
    result = build_site()
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_summary(args: argparse.Namespace) -> int:
    edition = load_edition(args.date)
    text = build_summary_text(edition)
    if args.json:
        _print_json({"edition_date": args.date, "preview": text})
    else:
        print(text, end="")
    return 0


def cmd_notify(args: argparse.Namespace) -> int:
    dry_run = not args.send
    # --send still blocked unless --i-understand-live AND a mock/injected path;
    # repository never loads secrets. --send without --mock raises via stub.
    sender = mock_sender if args.mock else None
    if args.send and not args.mock and not args.i_understand_live:
        print(
            "Refusing live send. Use default dry-run, or --mock for tests, "
            "or wire SendFn outside this repo after cutover.",
            file=sys.stderr,
        )
        return 2

    result = notify_edition(
        args.date,
        dry_run=dry_run,
        require_published=not args.allow_unpublished,
        published=args.published,
        force=args.force,
        sender=sender,
        state_path=Path(args.state) if args.state else None,
    )
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    ingest_result = ingest_inbox()
    if not ingest_result.get("ok"):
        _print_json({"stage": "ingest", **ingest_result})
        return 1
    build_result = build_site()
    date = args.date or (build_result.get("edition_dates") or [None])[0]
    notify_result = None
    if date:
        notify_result = notify_edition(
            date,
            dry_run=True,
            require_published=True,
            published=False,
        )
    _print_json(
        {
            "ingest": ingest_result,
            "build": build_result,
            "notify_preview": notify_result,
        }
    )
    return 0


def cmd_deps(_: argparse.Namespace) -> int:
    from vendor.box_inventory_bridge import dependency_report

    _print_json(dependency_report())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Unified runner. Always defaults to dry-run; never enables schedule."""
    if args.live:
        print(
            "Refusing --live in this CLI surface. Use dry-run offline runner; "
            "parent Bot cutover will wire live flags later.",
            file=sys.stderr,
        )
        return 2
    edition = None
    if args.date:
        edition = datetime.strptime(args.date, "%Y-%m-%d").date()
    cfg = RunConfig(
        edition_date=edition,
        dry_run=True,
        write_legacy_daily_html=bool(args.write_legacy_html),
        builder_feed=Path(args.builder_feed) if args.builder_feed else None,
        deals_feed=Path(args.deals_feed) if args.deals_feed else None,
        aihot_groups_file=Path(args.groups_file) if args.groups_file else None,
        skip_aihot_fetch=bool(args.skip_aihot),
        require_publish_for_notify=True,
        published=False,
    )
    result = run_unified(cfg)
    _print_json(run_result_to_dict(result))
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aihot_pipeline", description="AIHOT static pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("ingest", help="Validate & merge data/inbox/*.json")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("build", help="Render e/ builder/ deals/ pages from editions")
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("summary", help="Print Feishu summary preview text")
    s.add_argument("date", help="YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser("notify", help="Notify Feishu (default: dry-run)")
    s.add_argument("date", help="YYYY-MM-DD")
    s.add_argument("--send", action="store_true", help="Attempt send (still blocked without --mock)")
    s.add_argument("--mock", action="store_true", help="Use in-process mock sender")
    s.add_argument("--published", action="store_true", help="Mark site publish succeeded")
    s.add_argument(
        "--allow-unpublished",
        action="store_true",
        help="Bypass publish gate (still dry-run unless --send)",
    )
    s.add_argument("--force", action="store_true", help="Bypass anti-resend hash check")
    s.add_argument("--state", help="Override notify state path")
    s.add_argument(
        "--i-understand-live",
        action="store_true",
        help="Required together with custom external SendFn; stub still refuses secrets",
    )
    s.set_defaults(func=cmd_notify)

    s = sub.add_parser("pipeline", help="ingest + build + dry-run notify preview")
    s.add_argument("--date", help="Edition date for notify preview")
    s.set_defaults(func=cmd_pipeline)

    s = sub.add_parser(
        "run",
        help="Unified AIHOT+feeds runner (always dry-run; no schedule/live send)",
    )
    s.add_argument("--date", help="YYYY-MM-DD edition date (default: yesterday Asia/Shanghai)")
    s.add_argument("--groups-file", help="Offline AIHOT groups JSON")
    s.add_argument("--builder-feed", help="Builder channel feed JSON")
    s.add_argument("--deals-feed", help="Deals channel feed JSON (may be items:[])")
    s.add_argument("--skip-aihot", action="store_true", help="Skip AIHOT fetch/convert")
    s.add_argument(
        "--write-legacy-html",
        action="store_true",
        help="Also write YYYY-MM-DD.html from AIHOT items (off by default in CLI)",
    )
    s.add_argument(
        "--live",
        action="store_true",
        help="Rejected: live push/notify/CDP not enabled via this flag",
    )
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("deps", help="Report Chrome/CDP dependency probe (no network side effects)")
    s.set_defaults(func=cmd_deps)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
