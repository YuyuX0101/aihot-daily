"""CLI entrypoints for ingest / build / notify / summary / HTTP fetch."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .aihot_http import fetch_daily_report, resolve_daily_date
from .build import build_site
from .convert_aihot import official_report_to_daily_feed
from .ingest import ingest_inbox, load_edition
from .notify import mock_sender, notify_edition
from .paths import DATA_DIR, REPO_ROOT
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


def cmd_deps(args: argparse.Namespace) -> int:
    from vendor.box_inventory_bridge import dependency_report

    _print_json(dependency_report(probe_http=bool(args.probe_http)))
    return 0


def cmd_fetch_aihot(args: argparse.Namespace) -> int:
    """Read-only public HTTP fetch of official daily. Never publish/push/notify."""
    edition = None
    if args.date:
        edition = datetime.strptime(args.date, "%Y-%m-%d").date()
    base = args.base_url or "https://aihot.news"
    resolved = resolve_daily_date(edition, base_url=base, probe_latest=True)
    report, evidence = fetch_daily_report(resolved.edition_date, base_url=base)
    from dataclasses import asdict

    feed = official_report_to_daily_feed(report, evidence=asdict(evidence))
    out = {
        "ok": evidence.ok,
        "mode": "public_http_api",
        "date_resolution": {
            "edition_date": resolved.edition_date.isoformat(),
            "beijing_today": resolved.beijing_today.isoformat(),
            "hp_legacy_yesterday": resolved.hp_legacy_yesterday.isoformat(),
            "resolution": resolved.resolution,
            "latest_api_date": resolved.latest_api_date.isoformat()
            if resolved.latest_api_date
            else None,
            "note": resolved.note,
        },
        "evidence": asdict(evidence),
        "feed_item_count": len(feed["items"]),
        "titles": [it["title"] for it in feed["items"]],
        "official_page": (feed.get("source_meta") or {}).get("official_page"),
        "publish": {"attempted": False},
        "notify": {"attempted": False},
        "git_push": {"attempted": False},
    }

    if args.save_evidence:
        dest = Path(args.save_evidence)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(
                {"evidence": asdict(evidence), "report": report, "feed": feed},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out["saved_evidence"] = str(dest)

    if args.write_feed:
        feed_path = Path(args.write_feed)
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        feed_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out["written_feed"] = str(feed_path)

    _print_json(out)
    return 0 if evidence.ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Unified runner. Always defaults to dry-run; never enables schedule."""
    if args.live:
        print(
            "Refusing --live (push/notify cutover). "
            "Use --http-aihot for read-only public API ingest with dry-run gates.",
            file=sys.stderr,
        )
        return 2
    edition = None
    if args.date:
        edition = datetime.strptime(args.date, "%Y-%m-%d").date()
    use_http = bool(args.http_aihot)
    if args.groups_file and use_http:
        print("Pass only one of --http-aihot or --groups-file", file=sys.stderr)
        return 2
    if not args.skip_aihot and not use_http and not args.groups_file:
        print(
            "AIHOT source required: --http-aihot | --groups-file PATH | --skip-aihot",
            file=sys.stderr,
        )
        return 2
    cfg = RunConfig(
        edition_date=edition,
        dry_run=True,
        write_legacy_daily_html=bool(args.write_legacy_html),
        builder_feed=Path(args.builder_feed) if args.builder_feed else None,
        deals_feed=Path(args.deals_feed) if args.deals_feed else None,
        aihot_groups_file=Path(args.groups_file) if args.groups_file else None,
        use_http_aihot=use_http,
        aihot_base_url=args.base_url,
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
    s.add_argument(
        "--date",
        help="YYYY-MM-DD edition date (HTTP mode default: API latest daily date)",
    )
    s.add_argument(
        "--http-aihot",
        action="store_true",
        help="Read-only public GET https://aihot.news/api/v1/dailies (no browser/CDP)",
    )
    s.add_argument("--base-url", help="API base (default https://aihot.news)")
    s.add_argument(
        "--groups-file",
        help="Offline/parent-captured AIHOT groups JSON (HP DOM shape)",
    )
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
        help="Rejected: must not enable push/notify via this flag",
    )
    s.set_defaults(func=cmd_run)

    s = sub.add_parser(
        "fetch-aihot",
        help="Read-only fetch official daily via public HTTP API (no publish/push/notify)",
    )
    s.add_argument("--date", help="YYYY-MM-DD (default: API latest)")
    s.add_argument("--base-url", default="https://aihot.news")
    s.add_argument(
        "--save-evidence",
        help="Write evidence+report+feed JSON path",
    )
    s.add_argument("--write-feed", help="Write converted daily feed JSON path")
    s.set_defaults(func=cmd_fetch_aihot)

    s = sub.add_parser("deps", help="Report ingest dependencies (optional HTTP probe)")
    s.add_argument(
        "--probe-http",
        action="store_true",
        help="Perform one read-only GET /api/v1/dailies/latest",
    )
    s.set_defaults(func=cmd_deps)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
