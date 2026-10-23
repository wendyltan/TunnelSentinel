#!/usr/bin/env python3
"""Read only ChatGPT-family per-request route evidence from Shadowrocket.

Privacy invariant: output node labels, matched policy, hostname and timestamps
only; never emit requests URLs, User-Agent, cookies, subscription data, or
other web activity. Designed to be run as a bounded subprocess of the Guardian.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

DEFAULT_LOG_DIR = (
    Path.home()
    / "Library/Group Containers/group.com.liguangming.Shadowrocket/Library/Caches/Logs"
)

def allowed_host(value: str) -> str:
    raw = value.strip()
    if not raw or len(raw) > 4096:
        return ""
    try:
        value = urlsplit(raw if "://" in raw else "//" + raw).hostname or ""
    except ValueError:
        return ""
    host = value.lower().strip(".")
    if any(host == suffix or host.endswith("." + suffix)
           for suffix in ("chatgpt.com", "openai.com")):
        return host
    return ""


def parse_route(raw_url: str, raw_result: str, raw_time: str, group: str) -> dict | None:
    host = allowed_host(raw_url)
    if not host or not isinstance(raw_result, str):
        return None
    # Exact group matcher; a reference to a policy in a URL isn't evidence.
    pattern = r"(?:^|,)\s*" + re.escape(group) + r"\s*#\s*(.+?)\s*$"
    match = re.search(pattern, raw_result)
    if not match:
        return None
    name = match.group(1).strip()
    if not 1 <= len(name) <= 96 or any(ord(x) < 32 for x in name):
        return None
    try:
        when = datetime.strptime(str(raw_time), "%Y-%m-%d %H:%M:%S").astimezone()
    except (ValueError, TypeError):
        return None
    # Output deliberately omits raw_url/UA/raw policy result.
    return {
        "name": name,
        "host": host,
        "group": group,
        "observed_at": when.isoformat(timespec="seconds"),
        "epoch": int(when.timestamp()),
        "source": "shadowrocket_native_proxy_log",
    }


def scan_logs(directory: Path, group: str, limit: int = 400) -> dict:
    events = []
    try:
        candidates = sorted(directory.glob("proxy-*.db"),
                            key=lambda f: f.stat().st_mtime, reverse=True)[:3]
    except OSError:
        candidates = []
    for path in candidates:
        connection = None
        try:
            # Absolutely no transactions/writes, no scheme changes or GUI access.
            connection = sqlite3.connect(
                "file:" + str(path) + "?mode=ro",
                uri=True, timeout=0.3,
            )
            connection.execute("pragma query_only=ON")
            rows = connection.execute(
                "SELECT c0url,c2result,c4created FROM logging_content "
                "ORDER BY docid DESC LIMIT ?", (limit,)
            )
            for raw_url, raw_result, raw_date in rows:
                entry = parse_route(raw_url, raw_result, raw_date, group)
                if entry:
                    events.append(entry)
        except (sqlite3.Error, OSError):
            continue
        finally:
            if connection is not None:
                connection.close()
    # Deduplicate overlaps when files were rotated.
    keyed = {(e["epoch"], e["host"], e["name"]): e for e in events}
    ordered = sorted(keyed.values(), key=lambda e: e["epoch"], reverse=True)
    return {"latest": ordered[0] if ordered else None, "samples": ordered[:50],
            "source": "shadowrocket_native_proxy_log", "group": group}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    p.add_argument("--group", default="OpenAI-Resilience")
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,70}", args.group):
        return 2
    print(json.dumps(scan_logs(args.log_dir, args.group), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
