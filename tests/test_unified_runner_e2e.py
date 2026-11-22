"""Offline E2E: AIHOT fixture + real builder feed + deals0 → page + single notify preview."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools.aihot_pipeline import build as build_mod
from tools.aihot_pipeline import ingest as ingest_mod
from tools.aihot_pipeline import notify as notify_mod
from tools.aihot_pipeline import paths
from tools.aihot_pipeline.aihot_logic import filter_target_items
from tools.aihot_pipeline.feishu_gate import send_text
from tools.aihot_pipeline.notify import mock_sender, notify_edition
from tools.aihot_pipeline.unified_runner import RunConfig, run_unified


REPO = Path(__file__).resolve().parents[1]
GROUPS = REPO / "tests" / "fixtures" / "aihot_groups_2026-11-22.json"
BUILDER = REPO / "data" / "feeds" / "2026-11-22-builder.json"
DEALS = REPO / "data" / "feeds" / "2026-11-22-deals.json"


class AihotLogicWindowTests(unittest.TestCase):
    def test_cross_day_and_threshold(self):
        groups = json.loads(GROUPS.read_text(encoding="utf-8"))["groups"]
        items = filter_target_items(groups, date(2026, 11, 22), today=date(2026, 11, 22))
        titles = [i["title"] for i in items]
        self.assertEqual(len(items), 2)
        self.assertTrue(all("离线夹具" in t for t in titles))
        self.assertFalse(any("其他日期" in t for t in titles))
        self.assertFalse(any("低分" in t for t in titles))


class UnifiedRunnerE2ETests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aihot-e2e-"))
        self.editions = self.tmp / "editions"
        self.editions.mkdir()
        (self.tmp / "e").mkdir()
        (self.tmp / "builder").mkdir()
        (self.tmp / "deals").mkdir()
        # minimal template for optional legacy html
        shutil.copy(REPO / "daily-template.html", self.tmp / "daily-template.html")

        self._orig = {
            "EDITIONS_DIR": paths.EDITIONS_DIR,
            "EDITIONS_INDEX": paths.EDITIONS_INDEX,
            "EDITION_HTML_DIR": paths.EDITION_HTML_DIR,
            "BUILDER_DIR": paths.BUILDER_DIR,
            "DEALS_DIR": paths.DEALS_DIR,
            "DAYS_JSON": paths.DAYS_JSON,
            "NOTIFY_STATE": paths.NOTIFY_STATE,
            "REPO_ROOT": paths.REPO_ROOT,
        }
        paths.EDITIONS_DIR = self.editions
        paths.EDITIONS_INDEX = self.tmp / "editions_index.json"
        paths.EDITION_HTML_DIR = self.tmp / "e"
        paths.BUILDER_DIR = self.tmp / "builder"
        paths.DEALS_DIR = self.tmp / "deals"
        paths.DAYS_JSON = self.tmp / "days.json"
        paths.NOTIFY_STATE = self.tmp / "notify_state.json"
        paths.REPO_ROOT = self.tmp
        ingest_mod.EDITIONS_DIR = self.editions
        ingest_mod.EDITIONS_INDEX = paths.EDITIONS_INDEX
        build_mod.EDITIONS_DIR = self.editions
        build_mod.EDITION_HTML_DIR = paths.EDITION_HTML_DIR
        build_mod.BUILDER_DIR = paths.BUILDER_DIR
        build_mod.DEALS_DIR = paths.DEALS_DIR
        build_mod.DAYS_JSON = paths.DAYS_JSON
        build_mod.REPO_ROOT = self.tmp
        notify_mod.NOTIFY_STATE = paths.NOTIFY_STATE

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(paths, k, v)
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

    def test_e2e_page_and_single_notify_preview(self):
        cfg = RunConfig(
            edition_date=date(2026, 11, 22),
            dry_run=True,
            write_legacy_daily_html=True,
            aihot_groups_file=GROUPS,
            builder_feed=BUILDER,
            deals_feed=DEALS,
            repo_root=self.tmp,
            require_publish_for_notify=True,
            published=False,
            state_path=paths.NOTIFY_STATE,
        )
        r1 = run_unified(cfg)
        self.assertTrue(r1.ok, r1.error)
        self.assertIn("统一速报", r1.notify_preview or "")
        self.assertIn("Builder", r1.notify_preview or "")
        self.assertIn("不等于全网无优惠", r1.notify_preview or "")
        self.assertEqual(r1.stages["aihot_items"], 2)
        self.assertEqual(r1.stages["notify"].get("reason"), "site_not_published")

        page = (paths.EDITION_HTML_DIR / "2026-11-22.html").read_text(encoding="utf-8")
        self.assertIn("离线夹具：开源模型", page)
        self.assertIn("Prompt Puncher", page)
        self.assertIn("不等于全网无优惠", page)
        self.assertIn("北京时间", page)
        self.assertNotIn("example.com", page)

        legacy = self.tmp / "2026-11-22.html"
        self.assertTrue(legacy.exists())
        # fixture daily html stays in temp — not the GitHub Pages production tree

        # Same content notify mock: first send, second skip
        n1 = notify_edition(
            "2026-11-22",
            dry_run=False,
            require_published=True,
            published=True,
            sender=mock_sender,
            state_path=paths.NOTIFY_STATE,
        )
        self.assertTrue(n1.get("sent"))
        n2 = notify_edition(
            "2026-11-22",
            dry_run=False,
            require_published=True,
            published=True,
            sender=mock_sender,
            state_path=paths.NOTIFY_STATE,
        )
        self.assertTrue(n2.get("skipped"))
        self.assertEqual(n2.get("reason"), "already_sent_same_content")

        # feishu gate dry-run never sends
        g = send_text(r1.notify_preview or "", dry_run=True)
        self.assertFalse(g.get("sent"))
        self.assertTrue(g.get("dry_run"))

    def test_failure_skips_notify(self):
        cfg = RunConfig(
            edition_date=date(2026, 11, 22),
            dry_run=True,
            aihot_groups_file=GROUPS,
            builder_feed=REPO / "tests" / "examples" / "2026-11-21-builder.json",  # demo → fail
            deals_feed=DEALS,
            repo_root=self.tmp,
        )
        r = run_unified(cfg)
        self.assertFalse(r.ok)
        self.assertEqual(r.stages.get("notify", {}).get("reason"), "run_failed_no_notify")


if __name__ == "__main__":
    unittest.main()
