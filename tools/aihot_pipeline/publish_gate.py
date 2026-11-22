"""Gated git publish — default dry-run; never push main unless explicitly allowed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def is_git_push_allowed() -> bool:
    return os.environ.get("AIHOT_ALLOW_GIT_PUSH", "").strip() == "1"


def publish_repo(
    repo_dir: Path,
    *,
    message: str,
    dry_run: bool = True,
    remote: str = "origin",
    branch: str | None = None,
) -> dict[str, Any]:
    """Stage/commit optionally; push only when allowed and not dry-run.

    Unified runner should pass dry_run=True always until parent cutover.
    Pushing to main is further blocked unless AIHOT_ALLOW_PUSH_MAIN=1.
    """
    repo_dir = Path(repo_dir)
    branch = branch or os.environ.get("AIHOT_PUBLISH_BRANCH", "cursor/integrate-builder-deals-9c12")

    if dry_run or not is_git_push_allowed():
        return {
            "ok": True,
            "published": False,
            "dry_run": True,
            "reason": "dry_run" if dry_run else "git_push_not_allowed",
            "would_commit": message,
            "branch": branch,
        }

    if branch in {"main", "master"} and os.environ.get("AIHOT_ALLOW_PUSH_MAIN", "").strip() != "1":
        return {
            "ok": False,
            "published": False,
            "dry_run": False,
            "reason": "refusing_push_main_without_AIHOT_ALLOW_PUSH_MAIN",
            "branch": branch,
        }

    subprocess.run(["git", "-C", str(repo_dir), "add", "-A"], check=False, capture_output=True)
    commit = subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", message],
        capture_output=True,
        text=True,
    )
    nothing = "nothing to commit" in ((commit.stdout or "") + (commit.stderr or "")).lower()
    if commit.returncode != 0 and not nothing:
        return {
            "ok": False,
            "published": False,
            "dry_run": False,
            "reason": "commit_failed",
            "stderr": commit.stderr,
        }

    push = subprocess.run(
        ["git", "-C", str(repo_dir), "push", remote, branch],
        capture_output=True,
        text=True,
    )
    if push.returncode != 0:
        return {
            "ok": False,
            "published": False,
            "dry_run": False,
            "reason": "push_failed",
            "stderr": push.stderr,
        }
    return {"ok": True, "published": True, "dry_run": False, "branch": branch}
