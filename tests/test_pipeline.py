"""Deterministic tests for ingest / sanitize / notify / acceptance guards."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.aihot_pipeline import build as build_mod
from tools.aihot_pipeline import ingest as ingest_mod
from tools.aihot_pipeline import notify as notify_mod
from tools.aihot_pipeline import paths
from tools.aihot_pipeline.demo_guard import DemoGuardError, assert_production_feed
from tools.aihot_pipeline.render import render_channel_section, render_item
from tools.aihot_pipeline.sanitize import SanitizationError, validate_url
from tools.aihot_pipeline.summary import build_summary_text
from tools.aihot_pipeline.timefmt import format_beijing
from tools.aihot_pipeline.validate import ValidationError, load_and_validate_file, validate_feed


REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "tests" / "examples"
REAL_FEED = REPO / "data" / "feeds" / "2026-11-22-builder.json"


class SanitizeTests(unittest.TestCase):
    def test_rejects_javascript_url(self):
        with self.assertRaises(SanitizationError):
            validate_url("javascript:alert(1)")

    def test_accepts_https(self):
        self.assertEqual(validate_url("https://x.com/a"), "https://x.com/a")


class TimezoneTests(unittest.TestCase):
    def test_utc_z_to_beijing(self):
        text = format_beijing("2026-11-21T15:23:13.000Z")
        self.assertEqual(text, "2026-11-21 23:23 北京时间")
        self.assertNotIn("Z", text)

    def test_offset_to_beijing(self):
        text = format_beijing("2026-11-22T10:51:00+08:00")
        self.assertEqual(text, "2026-11-22 10:51 北京时间")

    def test_render_item_no_bare_z(self):
        html = render_item(
            {
                "id": "builder:1",
                "title": "t",
                "published_at": "2026-11-21T15:23:13.000Z",
                "verified_at": "2026-11-22T02:44:54.000Z",
                "author_claim": "claim",
                "verified_evidence": "evidence",
                "verification_tags": ["page_reachable", "author_claim", "untested"],
            },
            "builder",
        )
        self.assertIn("北京时间", html)
        self.assertNotRegex(html, r"\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")


class TagSemanticsTests(unittest.TestCase):
    def test_forbidden_verified_tag(self):
        raw = {
            "schema_version": "1.0",
            "edition_date": "2026-11-22",
            "channel": "builder",
            "source": "bot-x-web",
            "generated_at": "2026-11-22T10:51:00+08:00",
            "items": [
                {
                    "id": "builder:x",
                    "title": "t",
                    "verification_tags": ["verified"],
                }
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_feed(raw)
        self.assertIn("forbidden", str(ctx.exception).lower())

    def test_honesty_details_without_visible_tag_cluster(self):
        html = render_item(
            {
                "id": "builder:1",
                "title": "t",
                "author_claim": "作者自称本地不上传",
                "verified_evidence": "网页可打开；未实际上传测试",
                "verification_tags": ["page_reachable", "author_claim", "untested"],
                "notes": "页可打开≠隐私审计",
            },
            "builder",
        )
        self.assertIn("作者声明", html)
        self.assertIn("核验正文证据", html)
        self.assertIn("页面可达", html)
        self.assertNotIn('class="tag"', html)
        self.assertNotIn(">verified<", html.lower())


class DemoGuardTests(unittest.TestCase):
    def test_examples_require_allow_demo(self):
        with self.assertRaises(ValidationError):
            load_and_validate_file(EXAMPLES / "2026-11-21-builder.json", allow_demo=False)

    def test_examples_ok_with_allow_demo(self):
        doc = load_and_validate_file(EXAMPLES / "2026-11-21-builder.json", allow_demo=True)
        self.assertTrue(doc.get("demo"))

    def test_production_rejects_example_hosts(self):
        feed = {
            "schema_version": "1.0",
            "edition_date": "2026-11-22",
            "channel": "builder",
            "source": "bot-x-web",
            "generated_at": "2026-11-22T10:51:00+08:00",
            "items": [
                {
                    "id": "builder:evil",
                    "title": "fake",
                    "source_url": "https://example.com/x",
                    "verification_tags": ["page_reachable", "author_claim", "untested"],
                }
            ],
        }
        feed = validate_feed(feed)
        with self.assertRaises(DemoGuardError):
            assert_production_feed(feed)

    def test_demo_flag_blocked_in_production_guard(self):
        feed = load_and_validate_file(EXAMPLES / "2026-11-21-deals.json", allow_demo=True)
        with self.assertRaises(DemoGuardError):
            assert_production_feed(feed)


class EmptyDealsTests(unittest.TestCase):
    def test_zero_deals_message_not_fabricated(self):
        html = render_channel_section(
            "deals",
            [],
            meta={
                "empty_message": "本次未找到同时满足最近12小时新鲜度与可核验要求的新优惠（不等于全网无优惠）。"
            },
        )
        self.assertIn("0 条", html)
        self.assertIn("不等于全网无优惠", html)
        self.assertIn("is-empty", html)
        self.assertNotIn("LLM 推理额度", html)

    def test_empty_daily_links_legacy(self):
        html = render_channel_section(
            "daily",
            [],
            meta={"empty_message": "当日暂无 AI HOT 日报生成结果"},
            legacy_daily_href="../2026-11-20.html",
        )
        self.assertIn("2026-11-20.html", html)


class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aihot-test-"))
        self.inbox = self.tmp / "inbox"
        self.archive = self.tmp / "archive"
        self.editions = self.tmp / "editions"
        self.state = self.tmp / "state" / "notify_state.json"
        self.inbox.mkdir()
        self.archive.mkdir()
        self.editions.mkdir()

        self._orig = {
            "INBOX_DIR": paths.INBOX_DIR,
            "ARCHIVE_DIR": paths.ARCHIVE_DIR,
            "EDITIONS_DIR": paths.EDITIONS_DIR,
            "EDITIONS_INDEX": paths.EDITIONS_INDEX,
            "NOTIFY_STATE": paths.NOTIFY_STATE,
            "EDITION_HTML_DIR": paths.EDITION_HTML_DIR,
            "BUILDER_DIR": paths.BUILDER_DIR,
            "DEALS_DIR": paths.DEALS_DIR,
            "DAYS_JSON": paths.DAYS_JSON,
            "DATA_DIR": paths.DATA_DIR,
            "REPO_ROOT": paths.REPO_ROOT,
        }
        self._data = self.tmp / "data"
        self._data.mkdir()
        paths.INBOX_DIR = self.inbox
        paths.ARCHIVE_DIR = self.archive
        paths.EDITIONS_DIR = self.editions
        paths.EDITIONS_INDEX = self.tmp / "editions_index.json"
        paths.NOTIFY_STATE = self.state
        paths.EDITION_HTML_DIR = self.tmp / "e"
        paths.BUILDER_DIR = self.tmp / "builder"
        paths.DEALS_DIR = self.tmp / "deals"
        paths.DAYS_JSON = self.tmp / "days.json"
        paths.DATA_DIR = self._data
        paths.REPO_ROOT = self.tmp
        ingest_mod.INBOX_DIR = self.inbox
        ingest_mod.ARCHIVE_DIR = self.archive
        ingest_mod.EDITIONS_DIR = self.editions
        ingest_mod.EDITIONS_INDEX = paths.EDITIONS_INDEX
        build_mod.EDITIONS_DIR = self.editions
        build_mod.EDITION_HTML_DIR = paths.EDITION_HTML_DIR
        build_mod.BUILDER_DIR = paths.BUILDER_DIR
        build_mod.DEALS_DIR = paths.DEALS_DIR
        build_mod.DAYS_JSON = paths.DAYS_JSON
        build_mod.REPO_ROOT = self.tmp
        notify_mod.NOTIFY_STATE = self.state
        from tools.aihot_pipeline import home_snapshot as home_snap_mod

        self._home_snap_orig = home_snap_mod.HOME_SNAPSHOT
        self._home_data_orig = home_snap_mod.DATA_DIR
        home_snap_mod.DATA_DIR = self._data
        home_snap_mod.HOME_SNAPSHOT = self._data / "home_snapshot.json"

    def tearDown(self):
        from tools.aihot_pipeline import home_snapshot as home_snap_mod

        home_snap_mod.HOME_SNAPSHOT = self._home_snap_orig
        home_snap_mod.DATA_DIR = self._home_data_orig
        for k, v in self._orig.items():
            setattr(paths, k, v)
        ingest_mod.INBOX_DIR = self._orig["INBOX_DIR"]
        ingest_mod.ARCHIVE_DIR = self._orig["ARCHIVE_DIR"]
        ingest_mod.EDITIONS_DIR = self._orig["EDITIONS_DIR"]
        ingest_mod.EDITIONS_INDEX = self._orig["EDITIONS_INDEX"]
        build_mod.EDITIONS_DIR = self._orig["EDITIONS_DIR"]
        build_mod.EDITION_HTML_DIR = self._orig["EDITION_HTML_DIR"]
        build_mod.BUILDER_DIR = self._orig["BUILDER_DIR"]
        build_mod.DEALS_DIR = self._orig["DEALS_DIR"]
        build_mod.DAYS_JSON = self._orig["DAYS_JSON"]
        build_mod.REPO_ROOT = self._orig["REPO_ROOT"]
        notify_mod.NOTIFY_STATE = self._orig["NOTIFY_STATE"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_demo_fixture_cannot_enter_production_inbox(self):
        shutil.copy(EXAMPLES / "2026-11-21-builder.json", self.inbox / "demo.json")
        result = ingest_mod.ingest_inbox(self.inbox, self.archive)
        self.assertFalse(result["ok"])
        self.assertTrue(result["errors"])
        self.assertEqual(list(self.editions.glob("*.json")), [])

    def test_real_builder_feed_and_zero_deals(self):
        self.assertTrue(REAL_FEED.exists(), "committed real feed missing")
        shutil.copy(REAL_FEED, self.inbox / "builder.json")
        deals = {
            "schema_version": "1.0",
            "edition_date": "2026-11-22",
            "channel": "deals",
            "source": "bot-x-web",
            "generated_at": "2026-11-22T10:51:00+08:00",
            "channel_meta": {
                "empty_message": "本次未找到同时满足最近12小时新鲜度与可核验要求的新优惠（不等于全网无优惠）。"
            },
            "items": [],
        }
        (self.inbox / "deals.json").write_text(
            json.dumps(deals, ensure_ascii=False), encoding="utf-8"
        )
        result = ingest_mod.ingest_inbox(self.inbox, self.archive)
        self.assertTrue(result["ok"], result)
        edition = ingest_mod.load_edition("2026-11-22")
        self.assertEqual(len(edition["channels"]["builder"]["items"]), 5)
        self.assertEqual(len(edition["channels"]["deals"]["items"]), 0)
        self.assertIn("不等于全网无优惠", edition["channels"]["deals"]["meta"]["empty_message"])
        for item in edition["channels"]["builder"]["items"]:
            tags = set(item.get("verification_tags") or [])
            self.assertIn("untested", tags)
            self.assertIn("author_claim", tags)
            self.assertIn("page_reachable", tags)
            self.assertNotIn("verified", tags)
            self.assertTrue(item.get("author_claim"))
            self.assertTrue(item.get("verified_evidence"))

        text = build_summary_text(edition)
        self.assertIn("羊毛雷达 0 条", text)
        self.assertIn("不等于全网无优惠", text)
        self.assertNotIn("example.com", text)

        built = build_mod.build_site()
        self.assertTrue(built["ok"])
        page = (paths.EDITION_HTML_DIR / "2026-11-22.html").read_text(encoding="utf-8")
        self.assertIn("Prompt Puncher", page)
        self.assertIn("TextVeil", page)
        self.assertIn("北京时间", page)
        self.assertNotIn("example.com", page)
        self.assertNotRegex(page, r"\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")

    def test_notify_dry_run_and_anti_resend(self):
        shutil.copy(REAL_FEED, self.inbox / "builder.json")
        ingest_mod.ingest_inbox(self.inbox, self.archive)
        r0 = notify_mod.notify_edition(
            "2026-11-22",
            dry_run=True,
            require_published=True,
            published=False,
            state_path=self.state,
        )
        self.assertEqual(r0["reason"], "site_not_published")
        r1 = notify_mod.notify_edition(
            "2026-11-22",
            dry_run=False,
            require_published=True,
            published=True,
            sender=notify_mod.mock_sender,
            state_path=self.state,
        )
        self.assertTrue(r1["sent"])
        r2 = notify_mod.notify_edition(
            "2026-11-22",
            dry_run=False,
            require_published=True,
            published=True,
            sender=notify_mod.mock_sender,
            state_path=self.state,
        )
        self.assertTrue(r2["skipped"])
        self.assertEqual(r2["reason"], "already_sent_same_content")


class CommittedSiteAcceptanceTests(unittest.TestCase):
    """Guardrails against regressing fictional content into public pages."""

    def test_no_demo_edition_html(self):
        self.assertFalse((REPO / "e" / "2026-11-21.html").exists())
        self.assertFalse((REPO / "data" / "editions" / "2026-11-21.json").exists())

    def test_real_edition_page(self):
        page = (REPO / "e" / "2026-11-22.html").read_text(encoding="utf-8")
        self.assertIn("Prompt Puncher", page)
        self.assertIn("不等于全网无优惠", page)
        self.assertIn("北京时间", page)
        self.assertIn("作者声明", page)
        self.assertIn("核验正文证据", page)
        self.assertNotIn('class="tag"', page)
        self.assertNotIn("example.com", page)
        self.assertNotIn("OpenClaw", page)
        self.assertNotIn("LLM 推理额度", page)


if __name__ == "__main__":
    unittest.main()
