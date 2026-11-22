"""Lightweight accessibility / editorial regressions (no browser driver required)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class EditorialA11yTests(unittest.TestCase):
    def test_home_has_skip_and_nav(self):
        html = (REPO / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="skip-link"', html)
        self.assertIn('aria-label="主导航"', html)
        self.assertIn("assets/editorial.css", html)
        self.assertIn('href="e/index.html"', html)
        self.assertIn('id="today"', html)
        self.assertIn("今日统一期次", html)
        self.assertIn("网站预览", html)
        self.assertIn("尚未启用", html)
        self.assertIn('id="nav-toggle"', html)
        self.assertIn("data/home_snapshot.json", html)
        self.assertIn("功能预览", html)
        self.assertNotRegex(html, r"(?<!不代表)生产已迁移")

    def test_home_snapshot_has_real_builder_five(self):
        import json

        snap = json.loads((REPO / "data" / "home_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snap["edition_date"], "2026-11-22")
        self.assertEqual(snap["counts"]["builder"], 5)
        self.assertEqual(snap["counts"]["deals"], 0)
        self.assertGreaterEqual(snap["counts"]["daily"], 6)
        self.assertEqual(snap.get("daily_source_date"), "2026-11-22")
        self.assertTrue(
            (snap.get("daily_official_page") or "").startswith("https://aihot.news/daily/")
        )
        self.assertEqual(len(snap["builder_items"]), 5)
        for item in snap["builder_items"]:
            self.assertTrue(item.get("source_url", "").startswith("https://"))
            self.assertIn("北京时间", item.get("published_beijing") or "")
        self.assertIn("不等于全网无优惠", snap["deals_empty_message"])

    def test_edition_page_links_and_contrast_tokens(self):
        html = (REPO / "e" / "2026-11-22.html").read_text(encoding="utf-8")
        self.assertIn("skip-link", html)
        self.assertIn("editorial.css", html)
        self.assertIn("Prompt Puncher", html)
        self.assertIn("不等于全网无优惠", html)
        self.assertIn("北京时间", html)
        self.assertIn("未独立核验", html)
        self.assertIn("AIHOT 转载", html)
        self.assertIn("不等于原文发布时间", html)
        # focus style exists in CSS
        css = (REPO / "assets" / "editorial.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        self.assertIn("--ink:", css)
        self.assertIn("--paper:", css)

    def test_legacy_overlay_injected_without_wiping_body_copy(self):
        sample = (REPO / "2026-11-20.html").read_text(encoding="utf-8")
        self.assertIn("assets/legacy-daily-overlay.css", sample)
        self.assertIn("AI HOT 日报", sample)
        # original inline content markers remain
        self.assertIn("item-summary", sample)

    def test_contrast_rough_check_ink_on_paper(self):
        css = (REPO / "assets" / "editorial.css").read_text(encoding="utf-8")
        ink = re.search(r"--ink:\s*(#[0-9a-fA-F]{6})", css).group(1)
        paper = re.search(r"--paper:\s*(#[0-9a-fA-F]{6})", css).group(1)

        def lum(h: str) -> float:
            r, g, b = (int(h[i : i + 2], 16) / 255 for i in (1, 3, 5))

            def f(c: float) -> float:
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            R, G, B = f(r), f(g), f(b)
            return 0.2126 * R + 0.7152 * G + 0.0722 * B

        ratio = (lum(paper) + 0.05) / (lum(ink) + 0.05)
        if lum(ink) > lum(paper):
            ratio = (lum(ink) + 0.05) / (lum(paper) + 0.05)
        self.assertGreaterEqual(ratio, 7.0, f"contrast {ratio:.2f} for {ink} on {paper}")


if __name__ == "__main__":
    unittest.main()
