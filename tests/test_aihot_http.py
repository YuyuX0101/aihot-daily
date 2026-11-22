"""Offline tests for official daily HTTP convert + CDP stub honesty."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.aihot_pipeline.aihot_fetch import build_fetcher_from_env, DependencyGapError
from tools.aihot_pipeline.convert_aihot import official_report_to_daily_feed
from vendor import box_inventory_bridge as bridge

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "aihot_daily_api_2026-11-22.json"


class OfficialDailyConvertTests(unittest.TestCase):
    def test_fixture_converts_six_section_items(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        report = payload["report"]
        self.assertEqual(report["date"], "2026-11-22")
        feed = official_report_to_daily_feed(report)
        self.assertEqual(feed["edition_date"], "2026-11-22")
        self.assertEqual(feed["source"], "aihot-news-api-v1-dailies")
        self.assertEqual(len(feed["items"]), 6)
        urls = [it.get("source_url") for it in feed["items"]]
        self.assertTrue(all(u and u.startswith("https://aihot.news/items/") for u in urls))
        titles = [it["title"] for it in feed["items"]]
        self.assertTrue(any("Qwen4 Max" in t for t in titles))
        self.assertTrue(any("黎曼" in t for t in titles))
        # Must not be the older local HTML day masquerading as today
        self.assertNotEqual(feed["edition_date"], "2026-11-20")
        self.assertIn("aihot_daily_date", feed["source_meta"])
        for it in feed["items"]:
            self.assertIn("aihot_repost", it["verification_tags"])
            self.assertNotIn("verified", it["verification_tags"])
            self.assertNotIn("page_reachable", it["verification_tags"])


class FetcherConfigTests(unittest.TestCase):
    def test_no_cdp_fetcher_without_source(self):
        with self.assertRaises(DependencyGapError) as ctx:
            build_fetcher_from_env(prefer_http=False)
        msg = str(ctx.exception)
        self.assertIn("http-aihot", msg)
        self.assertIn("groups-file", msg)
        self.assertIn("CDP", msg)

    def test_cdp_stub_raises_clearly(self):
        with self.assertRaises(RuntimeError) as ctx:
            bridge.extract_groups_via_cdp("https://aihot.news/")
        self.assertIn("not implemented", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
