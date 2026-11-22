"""Feishu notification with dry-run default and anti-resend state."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .ingest import load_edition
from .paths import NOTIFY_STATE, SITE_BASE_URL
from .summary import build_summary_text


SendFn = Callable[[str], dict[str, Any]]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = path or NOTIFY_STATE
    if not path.exists():
        return {"sent": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or NOTIFY_STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mock_sender(text: str) -> dict[str, Any]:
    """Test double — never contacts external networks."""
    return {"ok": True, "mode": "mock", "bytes": len(text.encode("utf-8"))}


def real_sender_stub(text: str) -> dict[str, Any]:
    """Production hook placeholder.

    Intentionally does NOT read webhook secrets or send messages.
    Wire parent Bot's send_feishu_text externally when cutting over.
    """
    raise RuntimeError(
        "real Feishu send is disabled in this repository. "
        "Use --dry-run / --mock, or inject a SendFn from the parent Bot after cutover."
    )


def notify_edition(
    edition_date: str,
    *,
    dry_run: bool = True,
    require_published: bool = True,
    published: bool | None = None,
    state_path: Path | None = None,
    site_base: str = SITE_BASE_URL,
    sender: SendFn | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Build summary and optionally send. Default is dry-run (no send).

    Anti-resend: same edition_date + same content hash will not send again
    unless force=True.
    """
    edition = load_edition(edition_date)
    text = build_summary_text(edition, site_base=site_base)
    content_hash = _hash_text(text)

    if require_published and not published:
        return {
            "ok": True,
            "skipped": True,
            "reason": "site_not_published",
            "edition_date": edition_date,
            "preview": text,
            "content_hash": content_hash,
            "dry_run": dry_run,
        }

    state = load_state(state_path)
    sent = state.setdefault("sent", {})
    prev = sent.get(edition_date)
    if prev and prev.get("content_hash") == content_hash and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_sent_same_content",
            "edition_date": edition_date,
            "preview": text,
            "content_hash": content_hash,
            "dry_run": dry_run,
            "previous": prev,
        }

    if dry_run:
        return {
            "ok": True,
            "skipped": False,
            "sent": False,
            "dry_run": True,
            "edition_date": edition_date,
            "preview": text,
            "content_hash": content_hash,
        }

    send = sender or real_sender_stub
    result = send(text)
    sent[edition_date] = {
        "content_hash": content_hash,
        "sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": result.get("mode", "live"),
    }
    save_state(state, state_path)
    return {
        "ok": True,
        "skipped": False,
        "sent": True,
        "dry_run": False,
        "edition_date": edition_date,
        "preview": text,
        "content_hash": content_hash,
        "result": result,
    }
