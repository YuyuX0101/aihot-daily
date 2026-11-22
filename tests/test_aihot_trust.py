"""Trustworthiness guards for third-party AIHOT imports and Feishu summary tone."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.aihot_pipeline.convert_aihot import (
    AIHOT_EVIDENCE_STUB,
    AIHOT_IMPORT_TAGS,
    official_report_to_daily_feed,
)
from tools.aihot_pipeline.render import render_channel_section, render_item
from tools.aihot_pipeline.summary import build_summary_text
from tools.aihot_pipeline.validate import ValidationError, validate_feed

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "aihot_daily_api_2026-11-22.json"


class AihotImportHonestyTests(unittest.TestCase):
    def setUp(self):
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))["report"]
        self.feed = official_report_to_daily_feed(report)

    def test_never_auto_verified_or_page_reachable(self):
        for item in self.feed["items"]:
            tags = set(item.get("verification_tags") or [])
            self.assertTrue({"aihot_repost", "unverified_upstream", "untested"}.issubset(tags))
            self.assertNotIn("verified", tags)
            self.assertNotIn("tested", tags)
            self.assertNotIn("page_reachable", tags)
            self.assertEqual(tags, set(AIHOT_IMPORT_TAGS))

    def test_evidence_is_boundary_not_upstream_prose(self):
        for item in self.feed["items"]:
            self.assertEqual(item.get("verified_evidence"), AIHOT_EVIDENCE_STUB)
            self.assertNotIn("黎曼", item.get("verified_evidence") or "")
            self.assertNotIn("3SUM", item.get("verified_evidence") or "")
            self.assertIn("AIHOT 转载", item.get("notes") or "")
            self.assertIn("未独立核验", item.get("notes") or "")
            self.assertIn("【上游报道 · AIHOT 转载 · 未独立核验】", item.get("summary") or "")

    def test_upstream_source_name_and_urls_preserved(self):
        # Fixture contains Together AI / Ars / Rohan Paul etc.
        authors = {it.get("author") for it in self.feed["items"]}
        self.assertTrue(any("Together" in (a or "") for a in authors))
        self.assertTrue(any("Ars Technica" in (a or "") for a in authors))
        # Real original URLs kept separately from AIHOT attribution pages.
        with_original = [it for it in self.feed["items"] if it.get("playable_url")]
        self.assertGreaterEqual(len(with_original), 3)
        for it in with_original:
            self.assertFalse(
                it["playable_url"].startswith("https://aihot.news/"),
                msg="original URL must not be overwritten by AIHOT host",
            )
            if it.get("source_url"):
                self.assertTrue(
                    it["source_url"].startswith("https://aihot.news/items/"),
                    msg="AIHOT attribution page should remain source_url when present",
                )
        # No invented publish times when API daily sections omit them.
        for it in self.feed["items"]:
            self.assertIsNone(it.get("published_at"))

    def test_validate_accepts_honesty_tags_rejects_verified(self):
        ok = validate_feed(self.feed, allow_demo=False)
        self.assertEqual(len(ok["items"]), 6)
        bad = json.loads(json.dumps(self.feed))
        bad["items"][0]["verification_tags"] = ["verified", "untested"]
        with self.assertRaises(ValidationError):
            validate_feed(bad, allow_demo=False)


class SummaryToneTests(unittest.TestCase):
    def test_daily_summary_does_not_amplify_breakthrough_titles(self):
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))["report"]
        feed = official_report_to_daily_feed(report)
        edition = {
            "edition_date": "2026-11-22",
            "channels": {
                "daily": {"items": feed["items"], "meta": feed.get("channel_meta") or {}},
                "builder": {
                    "items": [
                        {
                            "id": "builder:1",
                            "title": "Prompt Puncher",
                            "score": 50,
                        }
                    ]
                },
                "deals": {
                    "items": [],
                    "meta": {
                        "empty_message": "本次未找到同时满足最近12小时新鲜度与可核验要求的新优惠（不等于全网无优惠）。"
                    },
                },
            },
        }
        text = build_summary_text(edition)
        self.assertIn("6 条（上游汇总，未独立核验）", text)
        self.assertNotIn("黎曼猜想", text)
        self.assertNotIn("3SUM", text)
        self.assertNotIn("金丝雀", text)
        # Builder titles still listed; deals empty honesty kept.
        self.assertIn("Prompt Puncher", text)
        self.assertIn("不等于全网无优惠", text)
        self.assertIn("完整内容：", text)

    def test_daily_render_disclaimer_and_labels(self):
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))["report"]
        feed = official_report_to_daily_feed(report)
        item_html = render_item(feed["items"][0], "daily")
        self.assertIn("上游报道（AIHOT 转载 · 未独立核验）", item_html)
        self.assertIn("本站核验边界", item_html)
        self.assertIn("原文发布时间未知", item_html)
        self.assertIn("摄取", item_html)
        self.assertNotIn(">核查 ", item_html)
        self.assertIn("原文链接（未核验）", item_html)
        section = render_channel_section(
            "daily",
            feed["items"],
            meta=feed.get("channel_meta") or {},
        )
        self.assertIn("section-disclaimer", section)
        self.assertIn("未独立核验", section)
        self.assertIn("不等于原文发布时间", section)


if __name__ == "__main__":
    unittest.main()
