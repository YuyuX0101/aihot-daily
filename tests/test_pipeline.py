"""Unit tests for ingest / sanitize / notify (no network)."""

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
from tools.aihot_pipeline.sanitize import SanitizationError, validate_url
from tools.aihot_pipeline.summary import build_summary_text
from tools.aihot_pipeline.validate import ValidationError, load_and_validate_file, validate_feed


REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures" / "mock"


class SanitizeTests(unittest.TestCase):
    def test_rejects_javascript_url(self):
        with self.assertRaises(SanitizationError):
            validate_url("javascript:alert(1)")

    def test_accepts_https(self):
        self.assertEqual(validate_url("https://example.com/a"), "https://example.com/a")


class ValidateTests(unittest.TestCase):
    def test_good_builder_fixture(self):
        doc = load_and_validate_file(FIXTURES / "2026-11-21-builder.json")
        self.assertEqual(doc["channel"], "builder")
        self.assertGreaterEqual(len(doc["items"]), 1)

    def test_rejects_injection_fixture(self):
        with self.assertRaises(ValidationError):
            load_and_validate_file(FIXTURES / "bad-injection.json")

    def test_deal_only_on_deals_channel(self):
        raw = {
            "schema_version": "1.0",
            "edition_date": "2026-11-21",
            "channel": "builder",
            "source": "t",
            "generated_at": "2026-11-21T00:00:00Z",
            "items": [
                {
                    "id": "x",
                    "title": "t",
                    "deal": {"threshold": "x"},
                }
            ],
        }
        with self.assertRaises(ValidationError):
            validate_feed(raw)


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

        # Redirect module paths
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
        }
        paths.INBOX_DIR = self.inbox
        paths.ARCHIVE_DIR = self.archive
        paths.EDITIONS_DIR = self.editions
        paths.EDITIONS_INDEX = self.tmp / "editions_index.json"
        paths.NOTIFY_STATE = self.state
        paths.EDITION_HTML_DIR = self.tmp / "e"
        paths.BUILDER_DIR = self.tmp / "builder"
        paths.DEALS_DIR = self.tmp / "deals"
        paths.DAYS_JSON = self.tmp / "days.json"
        ingest_mod.INBOX_DIR = self.inbox
        ingest_mod.ARCHIVE_DIR = self.archive
        ingest_mod.EDITIONS_DIR = self.editions
        ingest_mod.EDITIONS_INDEX = paths.EDITIONS_INDEX
        build_mod.EDITIONS_DIR = self.editions
        build_mod.EDITION_HTML_DIR = paths.EDITION_HTML_DIR
        build_mod.BUILDER_DIR = paths.BUILDER_DIR
        build_mod.DEALS_DIR = paths.DEALS_DIR
        build_mod.DAYS_JSON = paths.DAYS_JSON
        notify_mod.NOTIFY_STATE = self.state

    def tearDown(self):
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
        notify_mod.NOTIFY_STATE = self._orig["NOTIFY_STATE"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _copy_good_fixtures(self):
        for name in (
            "2026-11-21-builder.json",
            "2026-11-21-deals.json",
            "2026-11-21-daily.json",
        ):
            shutil.copy(FIXTURES / name, self.inbox / name)

    def test_ingest_dedup_and_build(self):
        self._copy_good_fixtures()
        # second copy of builder with same ids -> update path
        shutil.copy(
            FIXTURES / "2026-11-21-builder.json",
            self.inbox / "2026-11-21-builder-again.json",
        )
        result = ingest_mod.ingest_inbox(self.inbox, self.archive)
        self.assertTrue(result["ok"])
        edition = ingest_mod.load_edition("2026-11-21")
        self.assertEqual(len(edition["channels"]["builder"]["items"]), 2)
        self.assertEqual(len(edition["channels"]["deals"]["items"]), 2)

        text = build_summary_text(edition)
        self.assertIn("完整内容：", text)
        self.assertIn("/e/2026-11-21.html", text)
        self.assertIn("Builder", text)
        self.assertIn("羊毛", text)

        built = build_mod.build_site()
        self.assertTrue(built["ok"])
        page = (paths.EDITION_HTML_DIR / "2026-11-21.html").read_text(encoding="utf-8")
        self.assertIn("OpenClaw", page)
        self.assertIn("LLM 推理额度", page)
        # escaped / no raw script from good fixtures
        self.assertNotIn("<script>alert", page)

    def test_notify_dry_run_and_anti_resend(self):
        self._copy_good_fixtures()
        ingest_mod.ingest_inbox(self.inbox, self.archive)

        # Default: not published -> skip
        r0 = notify_mod.notify_edition(
            "2026-11-21",
            dry_run=True,
            require_published=True,
            published=False,
            state_path=self.state,
        )
        self.assertEqual(r0["reason"], "site_not_published")

        # Mock send once
        r1 = notify_mod.notify_edition(
            "2026-11-21",
            dry_run=False,
            require_published=True,
            published=True,
            sender=notify_mod.mock_sender,
            state_path=self.state,
        )
        self.assertTrue(r1["sent"])

        # Same content must not resend
        r2 = notify_mod.notify_edition(
            "2026-11-21",
            dry_run=False,
            require_published=True,
            published=True,
            sender=notify_mod.mock_sender,
            state_path=self.state,
        )
        self.assertTrue(r2["skipped"])
        self.assertEqual(r2["reason"], "already_sent_same_content")

        # Force allows resend
        r3 = notify_mod.notify_edition(
            "2026-11-21",
            dry_run=False,
            require_published=True,
            published=True,
            sender=notify_mod.mock_sender,
            state_path=self.state,
            force=True,
        )
        self.assertTrue(r3["sent"])


if __name__ == "__main__":
    unittest.main()
