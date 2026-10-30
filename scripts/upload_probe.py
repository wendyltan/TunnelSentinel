#!/usr/bin/env python3
"""Measure real uplink throughput through the local proxy.

Read-only: sends random bytes to a neutral echo endpoint and reports the bytes
the server actually received. Never touches ChatGPT, Codex or Shadowrocket.

Why this exists: node reachability and latency say nothing about upload speed.
On 2026-10-30 the working node had ~40-66 KB/s uplink, which is enough to make
a multi-megabyte Codex request time out mid-upload while every ping looked fine.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse

SOURCE = "bounded_upload_probe"
# postman-echo.com reads the whole body before answering; httpbingo/speed.cloudflare
# reject early and would report a fake (too fast) rate.
DEFAULT_URL = "https://postman-echo.com/post"
DEFAULT_SIZE = 1024 * 1024
DEFAULT_TIMEOUT = 75.0


def _host(url):
    try:
        return urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return ""


def probe(proxy=None, url=DEFAULT_URL, size=DEFAULT_SIZE, timeout=DEFAULT_TIMEOUT):
    """Return a bounded measurement; never raises."""
    result = {"source": SOURCE, "state": "unavailable", "url_host": _host(url),
              "bytes": 0, "seconds": 0.0, "kbps": 0.0, "http_code": 0, "at": int(time.time())}
    size = max(64 * 1024, int(size))
    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="uplink-probe-", suffix=".bin")
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(size))
        cmd = ["/usr/bin/curl", "-sS", "-o", "/dev/null", "--max-time", str(int(timeout)),
               "-X", "POST", "-H", "Content-Type: application/octet-stream",
               "--data-binary", "@" + path,
               "-w", "%{http_code} %{size_upload} %{time_total}",
               url]
        if proxy:
            cmd[1:1] = ["--proxy", str(proxy)]
        started = time.time()
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                   timeout=timeout + 15)
        elapsed = time.time() - started
        parts = (completed.stdout or "").split()
        if len(parts) == 3:
            code, uploaded, total = int(parts[0]), int(parts[1]), float(parts[2])
            seconds = total if total > 0 else elapsed
            result.update(bytes=uploaded, seconds=round(seconds, 2),
                          http_code=code,
                          kbps=round(uploaded / seconds / 1024.0, 1) if seconds > 0 else 0.0)
            # Only a fully delivered body is a trustworthy rate.
            result["state"] = "ok" if uploaded >= size * 0.95 else "partial"
        else:
            result["state"] = "partial"
    except (OSError, ValueError, subprocess.SubprocessError):
        result["state"] = "unavailable"
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    return result


if __name__ == "__main__":
    proxy_arg = sys.argv[1] if len(sys.argv) > 1 else None
    url_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_URL
    print(json.dumps(probe(proxy_arg, url_arg), ensure_ascii=False))
