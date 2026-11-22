"""Optional bridge to box-inventory CDP scrape (NOT used by default / offline tests).

The inventory generator module has import-time side effects (opens log file, mutates
sys.path). This bridge therefore does **not** import it wholesale.

Live scrape still needs: headed Chrome/Chromium, DISPLAY, network to aihot.virxact.com.
This environment is not asserted ready. Callers must set AIHOT_ALLOW_LIVE_FETCH=1.
"""

from __future__ import annotations

import os
import shutil
from typing import Any


def _chrome_probe() -> str | None:
    env = os.environ.get("AIHOT_CHROME_BIN")
    if env and os.path.isfile(env):
        return env
    for cand in (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        shutil.which("google-chrome-stable") or "",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ):
        if cand and os.path.isfile(cand):
            return cand
    return None


def dependency_report() -> dict[str, Any]:
    chrome = _chrome_probe()
    return {
        "allow_live_fetch": os.environ.get("AIHOT_ALLOW_LIVE_FETCH", "").strip() == "1",
        "chrome_binary": chrome,
        "display": os.environ.get("DISPLAY"),
        "inventory_generator": "vendor/box-inventory/aihot-daily-generator.py",
        "note": (
            "Inventory uses headed Chrome + CDP; headless historically failed on aihot. "
            "Do not claim full live scrape works until a dedicated CDP adapter is proven."
        ),
        "live_ready": False,  # intentionally never claimed true in this PR
    }


def extract_groups_via_cdp(aihot_url: str) -> list[dict[str, Any]]:
    report = dependency_report()
    raise RuntimeError(
        "Live CDP extract is intentionally not auto-executed in this repository adapter. "
        f"Probe={report}. Capture groups offline into AIHOT_GROUPS_FILE, or implement/"
        "prove a side-effect-free CDP adapter before enabling production scrape."
    )


def enrich_via_cdp(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report = dependency_report()
    raise RuntimeError(
        "Live CDP enrich is intentionally not auto-executed. "
        f"Probe={report}."
    )
