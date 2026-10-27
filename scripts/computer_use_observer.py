#!/usr/bin/env python3
"""Passive, local-only Computer Use evidence. Never reads tool arguments/results.

Local Codex history proves an invocation ended, not that a web/desktop task
achieved its intended effect. Cloud Computer Use may not appear on this Mac.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import time

SOURCE = "local_codex_computer_use_observer_v1"
DB = Path.home() / ".codex/thread_history_1.sqlite"
LOG_ROOT = Path.home() / "Library/Logs/com.openai.codex"
WINDOW_SECONDS = 1800
HISTORY_SECONDS = 86400
LIMIT = 4000
ALLOWED = {"completed", "failed", "inProgress"}


def _backend_running():
    try:
        p = subprocess.run(["/bin/ps", "-axo", "comm="], capture_output=True,
                           text=True, timeout=1.0, check=False)
        if p.returncode:
            return "unknown"
        return ("running" if any(line.strip().endswith("/SkyComputerUseService")
                 for line in p.stdout.splitlines()) else "not_running")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _last_ready(log_root, now):
    """Inspect bounded recent desktop logs, retaining only an event timestamp."""
    try:
        folder = log_root / datetime.fromtimestamp(now).strftime("%Y/%m/%d")
        files = sorted(folder.glob("*.log"), key=lambda f: f.stat().st_mtime,
                       reverse=True)[:5]
    except OSError:
        return 0
    found = 0
    for path in files:
        try:
            with path.open("rb") as f:
                f.seek(max(0, path.stat().st_size - 524288))
                chunk = f.read().decode("utf-8", errors="replace")
            for line in chunk.splitlines():
                if "browser_use_iab_backend_startup_ready" not in line:
                    continue
                match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z)", line)
                if match:
                    stamp = int(datetime.fromisoformat(match.group(1).replace(
                        "Z", "+00:00")).timestamp())
                    if 0 <= now - stamp <= HISTORY_SECONDS:
                        found = max(found, stamp)
        except (OSError, ValueError):
            continue
    return found


def scan(db=DB, log_root=LOG_ROOT, now=None, backend_state=None):
    now = time.time() if now is None else now
    backend = backend_state if backend_state is not None else _backend_running()
    if backend not in ("running", "not_running", "unknown"):
        backend = "unknown"
    ready_at = _last_ready(Path(log_root), now) if backend == "running" else 0
    execution = {"state": "unavailable", "window_seconds": WINDOW_SECONDS,
                 "latest_at": 0, "latest_status": "", "last_completed_at": 0,
                 "last_failed_at": 0, "recent_completed": 0, "recent_failed": 0}
    con = None
    try:
        con = sqlite3.connect(f"file:{Path(db)}?mode=ro", uri=True, timeout=.3)
        con.execute("PRAGMA query_only=ON")
        # JSON paths only: no prompts, script arguments, screenshots or results
        # leave SQLite, nor are they persisted in status.json.
        rows = con.execute("""
          SELECT created_at_ms, completed_at_ms,
                 json_extract(item_json, '$.status') AS status
          FROM (
            SELECT created_at_ms,completed_at_ms,item_json FROM thread_items
            WHERE item_type='mcpToolCall' ORDER BY rowid DESC LIMIT ?
          )
          WHERE json_extract(item_json, '$.server')='cua_repl'
            AND json_extract(item_json, '$.tool')='js'
          ORDER BY created_at_ms DESC
        """, (LIMIT,)).fetchall()
        execution["state"] = "ok"
        for created_ms, completed_ms, status in rows:
            if status not in ALLOWED:
                continue
            try:
                started = int(created_ms) / 1000
                ended = int(completed_ms) / 1000 if completed_ms else 0
            except (ValueError, TypeError):
                continue
            if not 0 <= now - started <= HISTORY_SECONDS:
                continue
            # Running calls are never counted as finished.
            at = ended if ended and started <= ended <= now + 5 else started
            if execution["latest_at"] == 0:
                execution["latest_at"] = int(at)
                execution["latest_status"] = status
            if status == "completed" and ended and 0 <= now - ended <= HISTORY_SECONDS:
                execution["last_completed_at"] = max(execution["last_completed_at"], int(ended))
                if now - ended <= WINDOW_SECONDS:
                    execution["recent_completed"] += 1
            elif status == "failed" and ended and 0 <= now - ended <= HISTORY_SECONDS:
                execution["last_failed_at"] = max(execution["last_failed_at"], int(ended))
                if now - ended <= WINDOW_SECONDS:
                    execution["recent_failed"] += 1
    except (sqlite3.Error, OSError, ValueError):
        pass
    finally:
        if con is not None:
            con.close()
    return {"source": SOURCE, "checked_at": int(now),
            "backend": {"state": backend, "observed_at": int(now) if backend != "unknown" else 0,
                        "startup_ready_at": ready_at},
            "execution": execution,
            "scope": "local_codex_cua_repl_only",
            "limitations": "completed_is_tool_invocation_not_task_success;cloud_actions_unobservable"}


if __name__ == "__main__":
    print(json.dumps(scan(), ensure_ascii=False, separators=(",", ":")))
