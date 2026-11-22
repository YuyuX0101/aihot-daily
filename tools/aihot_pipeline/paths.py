"""Repository-relative paths (no machine-specific absolute paths)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
INBOX_DIR = DATA_DIR / "inbox"
EDITIONS_DIR = DATA_DIR / "editions"
ARCHIVE_DIR = DATA_DIR / "archive"
STATE_DIR = DATA_DIR / "state"

TEMPLATES_DIR = REPO_ROOT / "templates"
SCHEMA_PATH = REPO_ROOT / "schema" / "feed.schema.json"

EDITION_HTML_DIR = REPO_ROOT / "e"
BUILDER_DIR = REPO_ROOT / "builder"
DEALS_DIR = REPO_ROOT / "deals"

DAYS_JSON = REPO_ROOT / "days.json"
EDITIONS_INDEX = DATA_DIR / "editions_index.json"
NOTIFY_STATE = STATE_DIR / "notify_state.json"

SITE_BASE_URL = "https://yuyux0101.github.io/aihot-daily"
