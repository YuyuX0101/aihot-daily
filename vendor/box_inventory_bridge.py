"""Dependency probe + legacy inventory pointers (no CDP execution).

Live AIHOT ingest for this repo is the public HTTP API (tools.aihot_pipeline.aihot_http).
The box-inventory CDP generator is reference-only; this bridge does not launch browsers.
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


def dependency_report(*, probe_http: bool = False) -> dict[str, Any]:
    """Report readiness. CDP is never claimed ready.

    When probe_http=True, performs one read-only GET /api/v1/dailies/latest.
    """
    base = {
        "preferred_live_mode": "public_http_api",
        "api_base": os.environ.get("AIHOT_URL", "https://aihot.news").rstrip("/"),
        "api_docs": [
            "https://aihot.news/llms.txt",
            "https://aihot.news/agent?tab=api",
            "https://aihot.news/openapi-v1.json",
        ],
        "allow_live_fetch_env": os.environ.get("AIHOT_ALLOW_LIVE_FETCH", "").strip() == "1",
        "http_fetch_env": os.environ.get("AIHOT_HTTP_FETCH", "").strip() == "1",
        "chrome_binary": _chrome_probe(),
        "display": os.environ.get("DISPLAY"),
        "inventory_generator_reference_only": "vendor/box-inventory/aihot-daily-generator.py",
        "cdp_adapter_implemented": False,
        "cdp_ready": False,
        "groups_file_fallback": (
            "Parent may supply AIHOT_GROUPS_FILE / --groups-file from external headed "
            "capture of https://aihot.news/ (computerUse). Not required when HTTP API works."
        ),
        "note": (
            "Do not use the unimplemented CDP stub. Prefer --http-aihot "
            "(GET /api/v1/dailies). Homepage HTML is bot-challenged; public REST is the path."
        ),
    }
    if not probe_http:
        base.update(
            {
                "http_api_ready": None,
                "live_ready": False,
                "live_ready_reason": (
                    "HTTP probe not run in this deps call (pass probe_http / "
                    "python3 -m tools.aihot_pipeline deps --probe-http). "
                    "CDP remains unimplemented."
                ),
            }
        )
        return base

    from tools.aihot_pipeline.aihot_http import probe_http_api

    probe = probe_http_api(base.get("api_base") or "https://aihot.news")
    base.update(probe)
    return base


def extract_groups_via_cdp(aihot_url: str) -> list[dict[str, Any]]:
    raise RuntimeError(
        "CDP extract is not implemented in this repository. "
        f"Requested url={aihot_url}. Use public HTTP: "
        "python3 -m tools.aihot_pipeline fetch-aihot --http "
        "or provide --groups-file from parent external capture."
    )


def enrich_via_cdp(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raise RuntimeError(
        "CDP enrich is not implemented. Official /api/v1/dailies already includes summaries."
    )
