"""Read-only public HTTP client for aihot.news (stdlib only).

Upstream docs (anonymous, no API key):
  - https://aihot.news/llms.txt
  - https://aihot.news/agent?tab=api
  - OpenAPI: https://aihot.news/openapi-v1.json

Primary path for AIHOT daily channel: GET /api/v1/dailies/{date}
  (also /api/v1/dailies/latest). This replaces the legacy headed-CDP homepage
  scrape. HTML homepage is bot-challenged and is NOT the supported ingest path.

Never publishes, pushes, or sends Feishu.
"""

from __future__ import annotations

import gzip
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .aihot_logic import default_target_date, shanghai_today

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_BASE = "https://aihot.news"
DEFAULT_UA = "aihot-pipeline-readonly/1.1 (+stdlib urllib; personal non-commercial dry-run)"


@dataclass
class HttpFetchEvidence:
    ok: bool
    base_url: str
    request_url: str
    http_status: int | None = None
    etag: str | None = None
    bytes: int = 0
    daily_date: str | None = None
    item_count: int = 0
    highlight_count: int = 0
    section_labels: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    generated_at: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    error: str | None = None
    fetched_at_beijing: str | None = None
    note: str = (
        "Public REST /api/v1/dailies — anonymous read-only. "
        "Not CDP/browser. Not a publish/push/notify action."
    )


@dataclass
class ResolvedDailyDate:
    edition_date: date
    beijing_today: date
    hp_legacy_yesterday: date
    resolution: str  # cli | api_latest | cli_mismatch_warning
    latest_api_date: date | None
    note: str


def _now_beijing_str() -> str:
    return datetime.now(tz=SHANGHAI).strftime("%Y-%m-%d %H:%M:%S 北京时间")


def http_get_json(
    url: str,
    *,
    timeout: float = 30.0,
    user_agent: str = DEFAULT_UA,
) -> tuple[dict[str, Any], dict[str, str], bytes]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        raw = resp.read()
        headers = {k: v for k, v in resp.headers.items()}
        if raw[:2] == b"\x1f\x8b" or headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"expected JSON object from {url}")
        return data, headers, raw


def resolve_daily_date(
    explicit: date | None = None,
    *,
    base_url: str = DEFAULT_BASE,
    probe_latest: bool = True,
) -> ResolvedDailyDate:
    """Pick the AIHOT official daily date.

    HP/box legacy: at ~12:00 scrape homepage for *yesterday* (score≥75).
    Official API: publishes structured daily each day ~08:00 Beijing as /dailies/{date}.

    Unified edition uses the official daily's own `date` field so we never label
    an older local YYYY-MM-DD.html as "today's" AIHOT daily.
    """
    today = shanghai_today()
    hp_y = default_target_date()
    latest: date | None = None
    if probe_latest:
        payload, _, _ = http_get_json(f"{base_url.rstrip('/')}/api/v1/dailies/latest")
        report = payload.get("report") or {}
        latest = date.fromisoformat(str(report["date"]))
    if explicit is not None:
        note = (
            f"CLI/explicit edition_date={explicit.isoformat()}; "
            f"beijing_today={today.isoformat()}; "
            f"hp_legacy_yesterday={hp_y.isoformat()}; "
            f"api_latest={latest.isoformat() if latest else 'n/a'}."
        )
        resolution = "cli"
        if latest and explicit != latest:
            resolution = "cli_mismatch_warning"
            note += (
                " Explicit date differs from API latest — using explicit; "
                "caller must not treat another day's local HTML as this edition."
            )
        return ResolvedDailyDate(
            edition_date=explicit,
            beijing_today=today,
            hp_legacy_yesterday=hp_y,
            resolution=resolution,
            latest_api_date=latest,
            note=note,
        )
    if latest is None:
        raise RuntimeError("cannot resolve daily date: no explicit date and API probe disabled/failed")
    return ResolvedDailyDate(
        edition_date=latest,
        beijing_today=today,
        hp_legacy_yesterday=hp_y,
        resolution="api_latest",
        latest_api_date=latest,
        note=(
            f"Using official API latest daily date={latest.isoformat()} "
            f"(beijing_today={today.isoformat()}, hp_legacy_yesterday={hp_y.isoformat()}). "
            "Do not substitute older local daily HTML."
        ),
    )


def fetch_daily_report(
    daily_date: date | str | None = None,
    *,
    base_url: str = DEFAULT_BASE,
) -> tuple[dict[str, Any], HttpFetchEvidence]:
    """GET /api/v1/dailies/latest or /api/v1/dailies/{date}. Read-only."""
    base = base_url.rstrip("/")
    if daily_date is None:
        url = f"{base}/api/v1/dailies/latest"
    else:
        if isinstance(daily_date, date):
            daily_date = daily_date.isoformat()
        url = f"{base}/api/v1/dailies/{daily_date}"
    evidence = HttpFetchEvidence(
        ok=False,
        base_url=base,
        request_url=url,
        fetched_at_beijing=_now_beijing_str(),
    )
    try:
        payload, headers, raw = http_get_json(url)
        report = payload.get("report")
        if not isinstance(report, dict) or not report.get("date"):
            raise ValueError("response missing report.date")
        evidence.http_status = 200
        evidence.etag = headers.get("ETag")
        evidence.bytes = len(raw)
        evidence.daily_date = str(report["date"])
        evidence.generated_at = report.get("generatedAt")
        evidence.window_start = report.get("windowStart")
        evidence.window_end = report.get("windowEnd")
        labels: list[str] = []
        urls: list[str] = []
        n = 0
        for sec in report.get("sections") or []:
            labels.append(str(sec.get("label") or ""))
            for it in sec.get("items") or []:
                n += 1
                link = ((it.get("links") or {}).get("aihot")) or ((it.get("links") or {}).get("original"))
                if link:
                    urls.append(str(link))
        evidence.item_count = n
        evidence.highlight_count = len(report.get("highlights") or [])
        evidence.section_labels = labels
        evidence.source_urls = urls
        evidence.ok = True
        return report, evidence
    except urllib.error.HTTPError as exc:
        evidence.http_status = exc.code
        evidence.error = f"HTTPError {exc.code}: {exc.reason}"
        raise
    except Exception as exc:
        evidence.error = f"{type(exc).__name__}: {exc}"
        raise


def report_to_raw_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten official daily sections into HP-like item dicts (dedupe by id/title)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for sec in report.get("sections") or []:
        label = str(sec.get("label") or "")
        for it in sec.get("items") or []:
            iid = str(it.get("id") or "")
            title = str(it.get("title") or "").strip()
            key = iid or title
            if not key or key in seen:
                continue
            seen.add(key)
            links = it.get("links") or {}
            source = it.get("source") or {}
            out.append(
                {
                    "id": iid,
                    "title": title,
                    "summary": str(it.get("summary") or "").strip(),
                    "reason": str(it.get("summary") or "").strip(),
                    "src": str(source.get("name") or ""),
                    "link": str(links.get("aihot") or links.get("original") or ""),
                    "original_url": str(links.get("original") or "") or None,
                    "score": int(it.get("score") or 0),
                    "section_label": label,
                    "time": "",
                }
            )
    return out


def probe_http_api(base_url: str = DEFAULT_BASE) -> dict[str, Any]:
    """Dependency probe: one read-only latest daily GET. No CDP/browser."""
    try:
        report, evidence = fetch_daily_report(None, base_url=base_url)
        return {
            "http_api_ready": True,
            "live_ready": True,
            "live_mode": "public_http_api",
            "live_ready_reason": (
                "Public anonymous GET /api/v1/dailies/latest succeeded. "
                "CDP/browser scrape is not used and not claimed."
            ),
            "cdp_ready": False,
            "base_url": base_url.rstrip("/"),
            "daily_date": evidence.daily_date,
            "item_count": evidence.item_count,
            "request_url": evidence.request_url,
            "etag": evidence.etag,
            "fetched_at_beijing": evidence.fetched_at_beijing,
            "lead_title": ((report.get("lead") or {}).get("title")),
        }
    except Exception as exc:
        return {
            "http_api_ready": False,
            "live_ready": False,
            "live_mode": "public_http_api",
            "live_ready_reason": f"HTTP API probe failed: {type(exc).__name__}: {exc}",
            "cdp_ready": False,
            "base_url": base_url.rstrip("/"),
            "error": str(exc),
        }
