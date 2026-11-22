"""Gated Feishu sender — never sends unless explicitly enabled + configured.

Default: dry-run / mock. Does not load secrets unless AIHOT_FEISHU_ENABLED=1.
When enabled, loads feishu-webhook.json from AIHOT_FEISHU_CONFIG / AIHOT_KIMI_WORK_DIR
via a local copy of the notify module API (signature compatible with vendor).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


class FeishuGateError(RuntimeError):
    pass


def _config_path() -> Path | None:
    env = os.environ.get("AIHOT_FEISHU_CONFIG")
    if env:
        return Path(env)
    work = os.environ.get("AIHOT_KIMI_WORK_DIR")
    if work:
        return Path(work) / "feishu-webhook.json"
    return None


def is_feishu_enabled() -> bool:
    return os.environ.get("AIHOT_FEISHU_ENABLED", "").strip() == "1"


def _sign(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _live_deliver(text: str, *, timeout: int = 15) -> dict[str, Any]:
    """Only reachable when AIHOT_FEISHU_ENABLED=1. Still refuses if config missing."""
    path = _config_path()
    if path is None or not path.is_file():
        raise FeishuGateError(
            "AIHOT_FEISHU_ENABLED=1 but feishu-webhook.json not found "
            "(set AIHOT_FEISHU_CONFIG or AIHOT_KIMI_WORK_DIR). Secrets are never committed."
        )
    # Load locally — do not log url/secret values.
    cfg = json.loads(path.read_text(encoding="utf-8"))
    url, secret = cfg.get("url"), cfg.get("secret")
    if not url or not secret:
        raise FeishuGateError("feishu-webhook.json missing url/secret fields")
    ts = str(int(time.time()))
    payload = {
        "msg_type": "text",
        "content": {"text": text},
        "timestamp": ts,
        "sign": _sign(secret, ts),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    ok = body.get("code") == 0 or body.get("StatusCode") == 0
    return {"ok": ok, "mode": "live", "response_code": body.get("code")}


def send_text(
    text: str,
    *,
    dry_run: bool = True,
    sender: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send or preview a single Feishu text message.

    Rules:
    - dry_run=True (default): never network; return preview
    - dry_run=False requires AIHOT_FEISHU_ENABLED=1 OR an injected mock sender
    - Legacy generator Top5 notify must not be called from unified runner
    """
    if dry_run and sender is None:
        return {
            "ok": True,
            "sent": False,
            "dry_run": True,
            "preview": text,
            "reason": "dry_run",
        }

    if sender is not None:
        result = sender(text)
        return {
            "ok": bool(result.get("ok", True)),
            "sent": True,
            "dry_run": False,
            "preview": text,
            "result": result,
        }

    if not is_feishu_enabled():
        return {
            "ok": True,
            "sent": False,
            "dry_run": False,
            "preview": text,
            "reason": "feishu_not_enabled",
            "hint": "set AIHOT_FEISHU_ENABLED=1 and provide config to allow live send",
        }

    live = _live_deliver(text)
    return {
        "ok": live.get("ok", False),
        "sent": bool(live.get("ok")),
        "dry_run": False,
        "preview": text,
        "result": live,
    }
