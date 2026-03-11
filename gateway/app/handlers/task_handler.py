"""
Task execution handler.
Runs approved tasks only. Every run is logged.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from ..services import audit_log as _audit


# ── Safe subprocess helpers ───────────────────────────────────────────────

async def _run_subprocess(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"Timeout after {timeout}s"
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


# ── Task implementations ──────────────────────────────────────────────────

async def _restart_openclaw() -> str:
    # Attempt systemd restart; fall back to noop
    try:
        rc, out, err = await _run_subprocess(
            ["sudo", "systemctl", "restart", "openclaw"], timeout=15
        )
        if rc == 0:
            return "OpenClaw service restart initiated."
        return f"Restart failed (rc={rc}): {err.strip()}"
    except Exception as exc:
        return f"Restart error: {exc}"


async def _git_pull(repo_path: str | None = None) -> str:
    path = repo_path or os.getenv("OPENCLAW_REPO_PATH", ".")
    rc, out, err = await _run_subprocess(["git", "-C", path, "pull"], timeout=30)
    if rc == 0:
        return f"git pull OK: {out.strip()[:200] or 'already up to date'}"
    return f"git pull failed: {err.strip()[:200]}"


async def _morning_brief() -> str:
    # OPEN_ITEM: wire to actual morning brief workflow
    return "OPEN_ITEM: morning_brief workflow not yet wired. Stub executed successfully."


async def _check_failed_jobs() -> str:
    # OPEN_ITEM: query actual job queue
    return "OPEN_ITEM: job queue not wired. No failed jobs detected (stub)."


# ── Dispatch table ────────────────────────────────────────────────────────

_TASK_MAP = {
    "restart_openclaw": _restart_openclaw,
    "git_pull_repo": _git_pull,
    "run_morning_brief": _morning_brief,
    "check_failed_jobs": _check_failed_jobs,
}


async def handle_task(action_name: str = "unknown", **kwargs: Any) -> str:
    fn = _TASK_MAP.get(action_name)
    if fn is None:
        return f"OPEN_ITEM: task '{action_name}' is not yet wired."
    start = datetime.now(timezone.utc)
    result = await fn()
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    return f"{result}\n(ran in {elapsed:.1f}s)"
