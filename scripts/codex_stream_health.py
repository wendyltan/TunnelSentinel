#!/usr/bin/env python3
"""Summarize Codex's own stream faults; never export response bodies or prompts."""
import json
from pathlib import Path
import sqlite3
import time

DB = Path.home() / ".codex/logs_2.sqlite"
WINDOW = 1800
TARGETS = {"codex_core::responses_retry", "codex_api::endpoint::responses_websocket"}

def scan(path=DB, now=None):
    now = time.time() if now is None else now
    counts = {"broken_pipe":0,"websocket_handshake":0,"connection_reset":0}
    newest = 0
    con = None
    try:
        con = sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True,timeout=0.2)
        con.execute("PRAGMA query_only=ON")
        # Recent tail only: avoid a full-text scan of a potentially large Codex database.
        rows = con.execute(
            "SELECT ts, target, feedback_log_body FROM "
            "(SELECT ts, target, feedback_log_body FROM logs ORDER BY id DESC LIMIT 4500)"
        )
        for ts, target, body in rows:
            if target not in TARGETS or not isinstance(ts,int) or not (0 <= now-ts <= WINDOW):
                continue
            kind = None
            text = str(body).lower()
            if "broken pipe" in text:
                kind = "broken_pipe"
            elif "handshake" in text and "websocket" in text:
                kind = "websocket_handshake"
            elif "connection reset" in text:
                kind = "connection_reset"
            if kind:
                counts[kind] += 1
                newest = max(newest, ts)
    except (sqlite3.Error, OSError):
        return {"source":"codex_read_only_sqlite","state":"unavailable","counts":counts,"last_at":0}
    finally:
        if con is not None:con.close()
    return {"source":"codex_read_only_sqlite","state":"ok","counts":counts,
            "last_at":newest,"scan_at":int(now)}


if __name__ == "__main__":
    print(json.dumps(scan(),ensure_ascii=False))
