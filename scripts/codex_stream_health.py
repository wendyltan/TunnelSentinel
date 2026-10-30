#!/usr/bin/env python3
"""Summarize Codex's own stream faults; never export response bodies or prompts."""
import json
from pathlib import Path
import sqlite3
import time
from codex_remote_control import scan as scan_remote_control

DB = Path.home() / ".codex/logs_2.sqlite"
WINDOW = 1800
FAILOVER_WINDOW = 210
# The transport itself (responses_websocket) plus the client's fallback line are
# the two places that reveal "upgrade succeeded, session then died".
TARGETS = {"codex_core::responses_retry", "codex_api::endpoint::responses_websocket",
           "codex_core::client"}
TAIL_ROWS = 6000


def _empty_counts():
    return {"broken_pipe": 0, "websocket_handshake": 0, "connection_reset": 0,
            "ws_closed_after_upgrade": 0, "http_fallbacks": 0}


def _classify(target, text):
    """Map one log line to exactly one counter name, or None.

    Order matters: a WebSocket that upgraded and then closed is NOT a handshake
    failure, and it must not be silently counted as healthy.
    """
    if "broken pipe" in text:
        return "broken_pipe"
    if "connection closed" in text or "connection_closed" in text:
        return "ws_closed_after_upgrade"
    if "handshake" in text and "websocket" in text:
        return "websocket_handshake"
    if "connection reset" in text:
        return "connection_reset"
    if "falling back to http" in text:
        return "http_fallbacks"
    return None


def scan(path=DB, now=None):
    now = time.time() if now is None else now
    counts = _empty_counts()
    recent_counts = _empty_counts()
    newest = 0
    upgrades_ok = 0
    con = None
    try:
        con = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=0.2)
        con.execute("PRAGMA query_only=ON")
        # Recent tail only: avoid a full-text scan of a potentially large Codex database.
        rows = con.execute(
            "SELECT ts, target, feedback_log_body FROM "
            "(SELECT ts, target, feedback_log_body FROM logs ORDER BY id DESC LIMIT %d)" % TAIL_ROWS
        )
        for ts, target, body in rows:
            if target not in TARGETS or not isinstance(ts, int) or not (0 <= now - ts <= WINDOW):
                continue
            text = str(body).lower()
            if (target == "codex_api::endpoint::responses_websocket"
                    and "successfully connected" in text):
                upgrades_ok += 1
            kind = _classify(target, text)
            if kind:
                counts[kind] += 1
                newest = max(newest, ts)
                if 0 <= now - ts <= FAILOVER_WINDOW:
                    recent_counts[kind] += 1
    except (sqlite3.Error, OSError):
        return {"source": "codex_read_only_sqlite", "state": "unavailable",
                "counts": counts, "recent_counts": recent_counts, "ws_upgrades_ok": 0,
                "last_at": 0, "classification": "unavailable",
                "remote_control": scan_remote_control(path, now)}
    finally:
        if con is not None:
            con.close()
    recent_errors = sum(recent_counts[k] for k in (
        "broken_pipe", "websocket_handshake", "connection_reset", "ws_closed_after_upgrade"))
    if recent_counts["ws_closed_after_upgrade"] or recent_counts["http_fallbacks"]:
        classification = "ws_degraded"
    elif recent_errors:
        classification = "stream_failing"
    else:
        classification = "ok"
    return {"source": "codex_read_only_sqlite", "state": "ok",
            "counts": counts, "recent_counts": recent_counts,
            "ws_upgrades_ok": upgrades_ok, "last_at": newest, "scan_at": int(now),
            "classification": classification,
            "remote_control": scan_remote_control(path, now)}


if __name__ == "__main__":
    print(json.dumps(scan(), ensure_ascii=False))
