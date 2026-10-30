#!/usr/bin/env python3
"""Keep ChatGPT's Shadowrocket path healthy without using account credentials."""

from __future__ import annotations

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import dataclasses
from datetime import datetime
import fcntl
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import plistlib
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Deque, Iterable, Optional
from workflow_health import evaluate as evaluate_workflow_health, update_timeline as update_workflow_timeline
from urllib.parse import urlencode, urlparse


APP_NAME = "OpenAILinkGuardian"
VERSION = "1.5.6"
DEFAULT_HOME = Path.home() / "Library" / "Application Support" / APP_NAME
DEFAULT_CONFIG = DEFAULT_HOME / "config.json"
DEFAULT_STATUS = DEFAULT_HOME / "status.json"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / APP_NAME
CODEX_LOG_ROOT = Path.home() / "Library" / "Logs" / "com.openai.codex"
UPLOAD_HISTORY_PATH = DEFAULT_HOME / "upload_node_history.json"
UPLOAD_HISTORY_MAX_ENTRIES = 20


def _load_upload_history(path: Path = UPLOAD_HISTORY_PATH) -> list:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = data.get("entries")
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]
    except (OSError, ValueError, TypeError):
        pass
    return []


def _save_upload_history(entries: list, path: Path = UPLOAD_HISTORY_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"source": "upload_node_history_v1", "entries": entries},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def record_upload_sample(ip: str, country: str, colo: str, kbps: float, at: int,
                         path: Path = UPLOAD_HISTORY_PATH, now: float | None = None,
                         max_age: float = 14 * 86400, node: str = "") -> list:
    """Remember measured uplink per node, falling back to the exit when unnamed.

    The selected server name is read from a bounded child process; when it is
    unavailable the entry is still useful, keyed by its exit IP and country.
    """
    node = (node or "").strip()[:120]
    now = time.time() if now is None else now
    entries = [e for e in _load_upload_history(path)
               if 0 <= now - int(e.get("at", 0) or 0) <= max_age]
    rate = round(float(kbps), 1)
    for entry in entries:
        if node:
            same = entry.get("node") == node
        else:
            same = ((entry.get("ip"), entry.get("country")) == (ip, country)
                    and not entry.get("node"))
        if same:
            if int(entry.get("at", 0) or 0) == int(at):
                # Status is written every ~10s; the same measurement must not be
                # counted (or re-written) more than once.
                return entries
            entry.update({"colo": colo, "kbps": rate, "at": int(at), "ip": ip,
                          "country": country, "node": node,
                          "samples": int(entry.get("samples", 0) or 0) + 1,
                          "best_kbps": max(float(entry.get("best_kbps", 0) or 0), rate)})
            break
    else:
        entries.append({"ip": ip, "country": country, "colo": colo, "node": node,
                        "kbps": rate, "best_kbps": rate, "at": int(at), "samples": 1})
    entries.sort(key=lambda e: float(e.get("kbps", 0) or 0), reverse=True)
    entries = entries[:UPLOAD_HISTORY_MAX_ENTRIES]
    try:
        _save_upload_history(entries, path)
    except OSError:
        pass
    return entries


def upload_recommendation(entries: list, current: dict, observed, low_kbps: float = 80.0) -> dict:
    """Advisory only. Never a trigger for changing routes."""
    outcome = {"state": "no_advice", "identity": "exit_ip_not_subscription_name"}
    cur_ip = getattr(observed, "egress_ip", "") or ""
    current_kbps = 0.0
    for entry in entries:
        if entry.get("ip") == cur_ip:
            current_kbps = float(entry.get("kbps", 0) or 0)
            break
    if not current_kbps:
        current_kbps = float(current.get("kbps", 0) or 0)
    best = None
    for entry in entries:
        if entry.get("ip") == cur_ip:
            continue
        rate = float(entry.get("kbps", 0) or 0)
        if rate < low_kbps:
            continue
        if best is None or rate > float(best.get("kbps", 0) or 0):
            best = entry
    if best and current_kbps > 0 and float(best["kbps"]) >= current_kbps * 1.5:
        outcome.update(state="switch_recommended", current_kbps=round(current_kbps, 1),
                       best_kbps=float(best["kbps"]), country=best.get("country", ""),
                       colo=best.get("colo", ""), ip=best.get("ip", ""),
                       at=int(best.get("at", 0) or 0))
    return outcome
SHADOWROCKET_PREF_DOMAIN = (
    Path.home()
    / "Library/Group Containers/group.com.liguangming.Shadowrocket/Library/Preferences"
    / "group.com.liguangming.Shadowrocket"
)
SHADOWROCKET_NODE_KEY = "group.com.liguangming.SelectedServerName"

DEFAULTS = {
    "enabled": True,
    "dry_run": False,
    "proxy": "http://127.0.0.1:1082",
    "check_interval_seconds": 30,
    "fast_check_interval_seconds": 10,
    "recovery_backoff_seconds": 900,
    "manual_change_grace_seconds": 30,
    "known_good_max_age_hours": 72,
    "startup_grace_seconds": 45,
    "failure_window_seconds": 150,
    "failures_before_switch": 3,
    "switch_cooldown_seconds": 300,
    "switch_settle_seconds": 3,
    # Let Shadowrocket's native fallback group own traffic routing when enabled.
    # The external selected-server URL scheme is not a reliable node switcher
    # in recent Shadowrocket/macOS builds. Keep tunnel reconnection independent.
    "native_fallback_enabled": False,
    "native_fallback_group": "",
    "proxy_backend_auto_detect_enabled": True,
    "clash_auto_failover_enabled": False,
    # Optional user-approved local Mihomo Unix socket; no TCP API exposure.
    "mihomo_socket_path": "",
    # A single explicit safety gate for ALL node-changing controllers.
    # Defaults read-only; the tunnel reconnect feature has its own switch.
    "automatic_control_enabled": False,
    "deep_connection_probe_enabled": True,
    "deep_connection_probe_interval_seconds": 300,
    # Measured uplink throughput. Latency and download speed do NOT predict
    # whether a multi-megabyte Codex request can be uploaded at all.
    "upload_probe_enabled": False,
    "upload_probe_interval_seconds": 900,
    "upload_probe_url": "https://postman-echo.com/post",
    "upload_probe_size_bytes": 1048576,
    # Supplemental public, unauthenticated AI-domain trace checks; never own
    # node selection and never escalate rate limits/geo lookups to a failure.
    "ai_matrix_enabled": False,
    "ai_matrix_interval_seconds": 900,
    # Read-only request-method comparison for the *currently selected* route.
    # Does NOT infer whether Shadowrocket native fallback itself uses HEAD.
    "endpoint_method_audit_enabled": False,
    # The user explicitly enabled native proxy logging for the requested
    # ChatGPT node identity feature. Never toggle logging on their behalf.
    "codex_stream_sqlite_monitor_enabled": False,
    "native_proxy_log_reader_enabled": False,
    "native_proxy_log_reader_interval_seconds": 40,
    "native_proxy_node_recent_seconds": 600,
    "tunnel_recovery_enabled": False,
    "tunnel_event_lookback_seconds": 300,
    "tunnel_reconnect_cooldown_seconds": 60,
    "tunnel_reconnect_settle_seconds": 3,
    # Legacy configured names must not be assumed to remain present in Shadowrocket.
    # Only nodes observed as working may be automatically attempted.
    "nodes": [],
    "initial_node": None,
    "probe_urls": {
        "edge": "https://chatgpt.com/cdn-cgi/trace",
    },
}

NETWORK_LOG_MARKERS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "tls handshake eof",
    "TLS handshake EOF",
    "Pausing imagegen due to network issues",
    "image generation failed: network error",
)

PUBSUB_FAILURE_MARKERS = (
    "chatgpt_pubsub_connection_failed",
    "ERR_CONNECTION_CLOSED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_TUNNEL_CONNECTION_FAILED",
)

PUBSUB_CLOSE_MARKER = "chatgpt_pubsub_transport_closed"
PUBSUB_OPEN_MARKER = "chatgpt_pubsub_transport_opened"
PUBSUB_OUTAGE_SECONDS = 45
PUBSUB_FAILURE_REPEAT_SECONDS = 30
ISSUE_WINDOW_SECONDS = 180
# Method adapted from the public Nexitally AI-routing test page:
# https://nxonearth.com/aitest.html
# The page executes requests in the visitor's own browser; it exposes no
# provider node-history feed. These are reachability/routing observations,
# NOT proof of ChatGPT login, prompt completions, or node-specific unlock.
AI_TRACE_TARGETS = (
    ("ChatGPT", "chatgpt.com"),
    ("OpenAI", "openai.com"),
    ("Sora", "sora.com"),
    ("Claude", "claude.ai"),
    ("Claude.com", "claude.com"),
    ("Grok", "grok.com"),
    ("Anthropic", "anthropic.com"),
    ("Perplexity", "www.perplexity.ai"),
)

ISSUE_LABELS = {
    "cloudflare": "ChatGPT 安全验证",
    "rate_limit": "ChatGPT 请求受限",
    "thread_sync": "会话列表同步失败",
    "connection": "ChatGPT 连接中断",
    "pubsub": "消息推送持续断开",
    "layout": "客户端布局异常",
    "browser_backend": "浏览器控制后台连接异常（需人工核实）",
}


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    name: str
    transport_ok: bool
    http_code: int
    challenged: bool
    duration: float
    detail: str = ""
    egress_ip: str = ""
    egress_colo: str = ""
    egress_country: str = ""


def parse_cloudflare_trace(body: str) -> tuple[str, str, str]:
    """Only accept a valid IP and bounded colo/country from the public edge.

    It measures an observed proxied request, not the identity of an upstream
    Shadowrocket server and not a promise for every separate connection.
    """
    attributes = {}
    for line in body.splitlines()[:35]:
        key, sep, value = line.partition("=")
        if sep and key in ("ip", "colo", "loc") and len(value) <= 55:
            attributes[key] = value.strip()
    try:
        ip = str(ipaddress.ip_address(attributes.get("ip", "")))
    except ValueError:
        return "", "", ""
    colo = attributes.get("colo", "")
    loc = attributes.get("loc", "")
    return ip, (colo if re.fullmatch(r"[A-Z]{3}", colo) else ""), (
        loc if re.fullmatch(r"[A-Z]{2}", loc) else ""
    )


def load_config(path: Path) -> dict:
    config = json.loads(json.dumps(DEFAULTS))
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            supplied = json.load(handle)
        for key, value in supplied.items():
            if key == "probe_urls" and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value
    return config


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "guardian.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if verbose or sys.stdout.isatty():
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


def is_cloudflare_challenge(headers: str, body: str) -> bool:
    text = f"{headers}\n{body}".lower()
    return any(
        marker in text
        for marker in (
            "cf-mitigated: challenge",
            "challenge-platform",
            "enable javascript and cookies to continue",
            "challenge-error-text",
        )
    )


def curl_probe(name: str, url: str, proxy: str, websocket: bool = False,
               http_head: bool = False) -> ProbeResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="openai-link-guardian-") as temp_dir:
        headers_path = Path(temp_dir) / "headers"
        body_path = Path(temp_dir) / "body"
        command = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "5",
            "--max-time",
            "10",
            "--dump-header",
            str(headers_path),
            "--output",
            str(body_path),
            "--write-out",
            "%{http_code}",
        ]
        # Explicit proxy follows macOS system route. If no explicit proxy is
        # configured, check the CURRENT transparent TUN/direct path without
        # inheriting unrelated HTTP_PROXY environment variables.
        command[3:3] = ["--proxy", proxy] if proxy else ["--noproxy", "*"]
        if websocket:
            command.extend(
                [
                    "--http1.1",
                    "--header",
                    "Connection: Upgrade",
                    "--header",
                    "Upgrade: websocket",
                    "--header",
                    "Sec-WebSocket-Version: 13",
                    "--header",
                    "Sec-WebSocket-Key: b3BlbmFpLWxpbmstZ3VhcmRpYW4=",
                ]
            )
        if http_head:
            command.append("--head")
        command.append(url)
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        headers = headers_path.read_text(encoding="utf-8", errors="replace") if headers_path.exists() else ""
        body = body_path.read_text(encoding="utf-8", errors="replace")[:64_000] if body_path.exists() else ""
    try:
        http_code = int((completed.stdout or "0").strip()[-3:])
    except ValueError:
        http_code = 0
    challenged = is_cloudflare_challenge(headers, body)
    transport_ok = completed.returncode == 0 and http_code > 0 and not challenged
    detail = completed.stderr.strip().replace("\n", " ")[:300]
    # Reuse the already-performed public edge request; no extra network
    # calls, no secret URLs and no temporary logging of the trace body.
    egress_ip, egress_colo, egress_country = (
        parse_cloudflare_trace(body)
        if (name.startswith("edge") or name.startswith("ai-")) and http_code == 200 and transport_ok
        and urlparse(url).path == "/cdn-cgi/trace" else ("", "", "")
    )
    return ProbeResult(
        name=name,
        transport_ok=transport_ok,
        http_code=http_code,
        challenged=challenged,
        duration=time.monotonic() - started,
        detail=detail,
        egress_ip=egress_ip,
        egress_colo=egress_colo,
        egress_country=egress_country,
    )


def ordered_candidates(nodes: list[str], current: Optional[str]) -> list[str]:
    if not nodes:
        return []
    if current not in nodes:
        return list(nodes)
    index = nodes.index(current)
    return nodes[index + 1 :] + nodes[: index + 1]


def select_shadowrocket_node(node: str, dry_run: bool) -> bool:
    if dry_run:
        return True
    url = "shadowrocket://select?" + urlencode({"s": node})
    try:
        completed = subprocess.run(
            ["/usr/bin/open", "-g", url],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        return completed.returncode == 0
    except subprocess.TimeoutExpired:
        # LaunchServices may keep `open` waiting while Shadowrocket has already
        # applied the URL action. The selected-node check is authoritative.
        return True


def current_shadowrocket_node(timeout: float = 2.0) -> Optional[str]:
    # Prefer CFPreferences state. A launchd agent can occasionally fail to
    # export that domain even when the on-disk group preference is readable.
    try:
        completed = subprocess.run(
            ["/usr/bin/defaults", "export", str(SHADOWROCKET_PREF_DOMAIN), "-"],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode == 0:
            node = plistlib.loads(completed.stdout).get(SHADOWROCKET_NODE_KEY)
            if isinstance(node, str) and node.strip():
                return node.strip()
        logging.getLogger(APP_NAME).debug("Shadowrocket defaults export exit=%s", completed.returncode)
    except (OSError, plistlib.InvalidFileException, subprocess.TimeoutExpired) as error:
        logging.getLogger(APP_NAME).debug("Shadowrocket defaults export failed type=%s", type(error).__name__)
    # Read via a bounded child process rather than blocking the guardian thread:
    # macOS may stall direct access to another app's Group Container.
    try:
        fallback = subprocess.run(
            ["/bin/cat", str(SHADOWROCKET_PREF_DOMAIN) + ".plist"],
            capture_output=True, check=False, timeout=1.0,
        )
        if fallback.returncode == 0:
            node = plistlib.loads(fallback.stdout).get(SHADOWROCKET_NODE_KEY)
            return node.strip() if isinstance(node, str) and node.strip() else None
    except (OSError, plistlib.InvalidFileException, subprocess.TimeoutExpired):
        pass
    return None


def wait_for_shadowrocket_node(node: str, timeout: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if current_shadowrocket_node() == node:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.2, remaining))


def proxy_endpoint_available(proxy: str, timeout: float = 0.5) -> bool:
    parsed = urlparse(proxy)
    if not parsed.hostname or not parsed.port:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout):
            return True
    except OSError:
        return False


def connect_shadowrocket_tunnel(dry_run: bool) -> bool:
    if dry_run:
        return True
    try:
        completed = subprocess.run(
            ["/usr/bin/open", "-g", "shadowrocket://connect"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        return completed.returncode == 0
    except subprocess.TimeoutExpired:
        # As with node selection, the URL action may already have reached the
        # app. The local proxy listener and health probe remain authoritative.
        return True


def latest_shadowrocket_stop_reason(lookback_seconds: int) -> str:
    """Return manual, failed, or unknown for the newest tunnel stop event."""
    seconds = max(60, int(lookback_seconds))
    command = [
        "/usr/bin/log",
        "show",
        "--style",
        "compact",
        "--last",
        f"{seconds}s",
        "--predicate",
        (
            'process == "nesessionmanager" AND '
            'eventMessage CONTAINS "Primary Tunnel:Shadowrocket"'
        ),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    for line in reversed(completed.stdout.splitlines()):
        if "last stop reason Stop command received" in line:
            return "manual"
        if "last stop reason Plugin failed" in line:
            return "failed"
    return "unknown"


def shadowrocket_app_still_running() -> bool:
    """Require current, exact executable provenance before a recovery action."""
    try:
        p = subprocess.run(["/bin/ps", "-axo", "comm="], text=True,
                           capture_output=True, check=False, timeout=2)
        return (p.returncode == 0 and
                "/Applications/Shadowrocket.app/Contents/MacOS/Shadowrocket"
                in p.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        return False


def read_known_good_nodes(path: Path, now: Optional[float] = None,
                          max_age_hours: float = 72) -> list[str]:
    """Extract *display names only* from previous successful public edge checks.

    Each candidate still requires exact selection confirmation and a NEW
    transport probe. This history is not proof that a node is working now.
    """
    now = time.time() if now is None else now
    if max_age_hours <= 0:
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 4_000_000))
            rows = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    seen: dict[str, float] = {}
    for row in rows:
        found = re.match(
            r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ INFO health=ok node=(.+?) "
            r"score=\d+ probes=edge:200:ok", row,
        )
        if not found:
            continue
        try:
            stamp = datetime.strptime(found.group(1), "%Y-%m-%d %H:%M:%S").astimezone().timestamp()
        except ValueError:
            continue
        node = found.group(2).strip()
        if node and len(node) <= 160 and 0 <= now - stamp <= max_age_hours * 3600:
            seen[node] = max(seen.get(node, 0.0), stamp)
    return [node for node, _ in sorted(seen.items(), key=lambda item: -item[1])]


class LogWatcher:
    def __init__(self, root: Path):
        self.root = root
        self.offsets: dict[str, int] = {}
        self.initialized = False
        self.pubsub_closed_at: dict[str, float] = {}
        self.pubsub_last_failure_at: dict[str, float] = {}
        self.issue_events: Deque[tuple[float, str]] = collections.deque(maxlen=1000)

    @staticmethod
    def classify_issue(line: str) -> Optional[str]:
        """Describe actual desktop-app failures, without treating them as proxy failures."""
        if "cloudflare_challenge" in line:
            return "cloudflare"
        if any(marker in line for marker in (
            "Too many requests", "fetch failed (429)", "HTTP 429"
        )):
            return "rate_limit"
        # A 403 from the authenticated thread catalog is a real desktop
        # sync failure even when the unauthenticated public edge returns 200.
        # It is a business diagnostic, never a reason to rotate proxy nodes.
        if "Thread catalog sync failed" in line:
            return "thread_sync"
        if "ERR_CONNECTION_CLOSED" in line or "ERR_PROXY_CONNECTION_FAILED" in line:
            return "connection"
        if "IAB_LIFECYCLE" in line and "iab backend info request failed" in line:
            return "browser_backend"
        if "ResizeObserver loop completed with undelivered notifications" in line:
            return "layout"
        return None

    def issue_summary(self) -> list[dict]:
        now = time.time()
        while self.issue_events and now - self.issue_events[0][0] > ISSUE_WINDOW_SECONDS:
            self.issue_events.popleft()
        groups: dict[str, list[float]] = {}
        for timestamp, category in self.issue_events:
            groups.setdefault(category, []).append(timestamp)
        # A solitary layout warning is routine; repeated warnings are actionable UX evidence.
        return sorted(
            (
                {
                    "category": kind,
                    "title": ISSUE_LABELS[kind],
                    "count": len(events),
                    "last_seen": max(events),
                }
                for kind, events in groups.items()
                if kind != "layout"  # Layout warnings are not network or browser-control failures.
            ),
            key=lambda item: item["last_seen"],
            reverse=True,
        )[:5]

    def _files(self) -> Iterable[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*/*/*/*.log"), key=lambda p: p.stat().st_mtime)[-20:]

    @staticmethod
    def _is_actionable(line: str) -> bool:
        if any(marker in line for marker in NETWORK_LOG_MARKERS):
            return True
        if "backend-api/codex/images/generations" in line:
            return any(
                marker in line.lower()
                for marker in ("network error", "request_failed", "connection failed", "timeout")
            )
        return all(marker in line for marker in PUBSUB_FAILURE_MARKERS[:1]) and any(
            marker in line for marker in PUBSUB_FAILURE_MARKERS[1:]
        )

    def _track_pubsub_transport(self, line: str) -> None:
        match = re.search(r"rendererWebContentsId=(\d+)", line)
        renderer = match.group(1) if match else "primary"
        if PUBSUB_OPEN_MARKER in line:
            self.pubsub_closed_at.pop(renderer, None)
            self.pubsub_last_failure_at.pop(renderer, None)
        elif (
            PUBSUB_CLOSE_MARKER in line
            and "windowFocused=true" in line
            and renderer not in self.pubsub_closed_at
        ):
            self.pubsub_closed_at[renderer] = time.monotonic()
            self.pubsub_last_failure_at.pop(renderer, None)

    def read_new_failures(self) -> list[str]:
        failures: list[str] = []
        files = list(self._files())
        if not self.initialized:
            for path in files:
                try:
                    size = path.stat().st_size
                    self.offsets[str(path)] = size
                    with path.open("rb") as handle:
                        handle.seek(max(0, size - 65_536))
                        for line in handle.read().decode("utf-8", errors="replace").splitlines():
                            self._track_pubsub_transport(line)
                            # Recover only recent app warnings on daemon restart. Never
                            # count historical events toward automatic node switching.
                            category = self.classify_issue(line)
                            if category:
                                match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z)", line)
                                if match:
                                    try:
                                        seen = datetime.fromisoformat(match.group(1).replace("Z", "+00:00")).timestamp()
                                    except ValueError:
                                        continue
                                    if 0 <= time.time() - seen <= ISSUE_WINDOW_SECONDS:
                                        self.issue_events.append((seen, category))
                except OSError:
                    continue
            self.initialized = True
            return failures
        for path in files:
            key = str(path)
            try:
                size = path.stat().st_size
                offset = self.offsets.get(key, 0)
                if size < offset:
                    offset = 0
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(offset)
                    for line in handle:
                        self._track_pubsub_transport(line)
                        category = self.classify_issue(line)
                        if category:
                            self.issue_events.append((time.time(), category))
                        if self._is_actionable(line):
                            failures.append(line.strip()[:500])
                    self.offsets[key] = handle.tell()
            except OSError:
                continue
        active = {str(path) for path in files}
        self.offsets = {path: offset for path, offset in self.offsets.items() if path in active}
        now = time.monotonic()
        for renderer, closed_at in self.pubsub_closed_at.items():
            if (
                now - closed_at >= PUBSUB_OUTAGE_SECONDS
                and now - self.pubsub_last_failure_at.get(renderer, 0.0)
                >= PUBSUB_FAILURE_REPEAT_SECONDS
            ):
                failures.append("ChatGPT PubSub transport remained closed for 45 seconds")
                self.issue_events.append((time.time(), "pubsub"))
                self.pubsub_last_failure_at[renderer] = now
        return failures


def correlate_client_events(stream: dict, computer_use: dict, now: float) -> dict:
    """Bounded time-only correlation, NEVER a shared-task or causal claim."""
    base={"source":"local_client_timestamp_comparison_v1",
          "state":"unverified","scope":"temporal_overlap_only_not_causal_or_task_completion"}
    execution=computer_use.get("execution") or {}
    if stream.get("state") != "ok" or execution.get("state") != "ok":
        return base
    try:
        counts=stream.get("recent_counts") or {}
        errors=sum(max(0,int(counts.get(k,0))) for k in (
            "broken_pipe","websocket_handshake","connection_reset"))
        stream_at=int(stream.get("last_at") or 0)
        tool_at=int(execution.get("latest_at") or 0)
        if not(errors and 0<=now-stream_at<=1800 and 0<=now-tool_at<=1800):
            return dict(base,state="no_recent_overlap")
        delta=abs(stream_at-tool_at)
        if delta>120:
            return dict(base,state="no_recent_overlap")
        return dict(base,state="nearby_events",gap_seconds=delta,
                    codex_error_at=stream_at,local_tool_at=tool_at,
                    local_tool_status=str(execution.get("latest_status",""))[:18])
    except (TypeError,ValueError):
        return base


class Guardian:
    def __init__(self, config: dict, logger: logging.Logger, status_path: Path):
        self.config = config
        # Legacy constructor default until the first real system-route cycle;
        # no proprietary node preferences are read at construction.
        self.active_backend = "shadowrocket"
        # Ephemeral ownership lease: only a listener proven in THIS running
        # Guardian process can qualify for one conservative missing-tunnel
        # recovery. Never persist the lease or infer it from a port alone.
        self.verified_shadowrocket_endpoint = ""
        self.verified_shadowrocket_at = 0.0
        self.missing_tunnel_reconnect_used = False
        self.system_route_observation: dict = {}
        self.route_generation = 0
        self.clash_observation: dict = {}
        self.logger = logger
        self.status_path = status_path
        self.log_watcher = LogWatcher(CODEX_LOG_ROOT)
        self.failure_times: Deque[float] = collections.deque()
        # Display-only confirmation, never a node switching trigger.
        self.consecutive_public_failures = 0
        self.last_switch_at = 0.0
        self.last_tunnel_reconnect_at = 0.0
        self.started_at = time.monotonic()
        self.recovery_state = "monitoring"
        self.recovery_reason = ""
        self.recovery_attempt_count = 0
        self.recovery_retry_at = 0.0
        self.manual_override_until = 0.0
        self.last_probe_results: list[ProbeResult] = []
        # Passive evidence of actual public-edge outages; never equate an
        # IP change with verified Shadowrocket backend selection.
        self.edge_last_healthy_ip = ""
        self.edge_outage_started_at: Optional[float] = None
        self.edge_outage_previous_ip = ""
        self.last_public_edge_incident: dict = {}
        # Passive, 2-sample-confirmed egress history. This is not a verified
        # Shadowrocket backend switch and never controls the proxy.
        self.confirmed_egress: tuple[str, str, str] | None = None
        self.pending_egress: tuple[str, str, str] | None = None
        self.pending_egress_count = 0
        self.egress_changed_at: list[dict] = []
        self.last_edge_recovered_at = 0.0
        self.ai_matrix_lock = threading.Lock()
        self.ai_matrix_started_at = 0.0
        self.ai_matrix_running = False
        self.ai_matrix_checked_at = 0.0
        self.ai_matrix_checks: list[dict] = []
        self.endpoint_method_audit: dict = {}
        self.codex_stream_lock = threading.Lock()
        self.codex_stream_last_run = 0.0
        self.codex_stream_running = False
        self.codex_stream_result: dict = {}
        self.computer_use_lock = threading.Lock()
        self.computer_use_running = False
        self.computer_use_last_run = 0.0
        self.computer_use_result: dict = {}
        self.deep_probe_lock = threading.Lock()
        self.deep_probe_running = False
        self.deep_probe_last_run = 0.0
        self.deep_probe_result: dict = {}
        self.upload_probe_lock = threading.Lock()
        self.upload_probe_running = False
        self.upload_probe_last_run = 0.0
        self.upload_probe_result: dict = {}
        self.node_name_lock = threading.Lock()
        self.node_name_running = False
        self.node_name_last_run = 0.0
        self.node_name_result: dict = {}
        self.native_log_lock = threading.Lock()
        self.native_log_last_run_at = 0.0
        self.native_log_running = False
        self.native_log_latest: dict = {}
        self.native_log_history: list[dict] = []
        self.native_log_error = ""
        self.healthy_streak_node: Optional[str] = None
        self.healthy_streak_count = 0
        self.learned_good_nodes = read_known_good_nodes(
            DEFAULT_LOG_DIR / "guardian.log",
            max_age_hours=float(config.get("known_good_max_age_hours", 72)),
        )
        self.known_good_cache_updated_at = time.monotonic()
        self.stop_requested = False
        self.refresh_requested = False
        previous_status = self._load_previous_status()
        self.manual_pause = bool(previous_status.get("manual_pause", False))
        last_log = previous_status.get("native_proxy_last_connection", {})
        if isinstance(last_log, dict) and last_log.get("source") == "shadowrocket_native_proxy_log":
            self.native_log_latest = {
                k: last_log[k] for k in ("name","host","group","observed_at","epoch","source")
                if k in last_log
            }
        stored_routes = previous_status.get("native_proxy_node_history", [])
        if isinstance(stored_routes, list):
            self.native_log_history = [
                item for item in stored_routes[-10:]
                if isinstance(item, dict) and item.get("source") == "shadowrocket_native_proxy_log"
            ]
        stored_changes = previous_status.get("egress_change_history", [])
        if isinstance(stored_changes, list):
            self.egress_changed_at = [
                e for e in stored_changes[-6:]
                if isinstance(e, dict) and
                e.get("evidence") == "confirmed_public_edge_egress_change" and
                e.get("native_backend_switch_verified") is False
            ]
        nodes = list(config.get("nodes", []))
        previous_node = previous_status.get("current_node")
        # Auto-backend sessions cannot assume Shadowrocket owns this Mac.
        # Its protected App Group preference is only read after the runtime
        # selector has explicitly confirmed a Shadowrocket proxy owner.
        # Never consult another app's protected preference during startup.
        # Legacy manual node switching is no longer a supported auto route.
        observed_node = None
        # In automatic system-route mode never resurrect a historical vendor
        # selection from an old status file or a deleted policy group.
        self.current_node = (None if config.get("proxy_backend_auto_detect_enabled",False)
                             else config.get("initial_node") or (nodes[0] if nodes else None))
        self.current_node_verified = observed_node is not None

    def _codex_stream_worker(self) -> None:
        helper = DEFAULT_HOME / "codex_stream_health.py"
        result = {"state":"unavailable","source":"codex_read_only_sqlite"}
        try:
            proc = subprocess.run([sys.executable, str(helper)],
                                  capture_output=True,text=True,check=False,timeout=2.5)
            if proc.returncode == 0:
                parsed = json.loads(proc.stdout)
                if parsed.get("source") == "codex_read_only_sqlite":
                    result = parsed
        except (OSError,TypeError,ValueError,subprocess.SubprocessError):
            pass
        finally:
            with self.codex_stream_lock:
                self.codex_stream_result = result
                self.codex_stream_running = False

    def maybe_begin_codex_stream(self) -> None:
        if not self.config.get("codex_stream_sqlite_monitor_enabled",False):
            return
        now=time.monotonic()
        with self.codex_stream_lock:
            if self.codex_stream_running or now-self.codex_stream_last_run<45:
                return
            self.codex_stream_running=True
            self.codex_stream_last_run=now
        threading.Thread(target=self._codex_stream_worker,daemon=True,
                         name="CodexStreamHealthObserver").start()

    def _computer_use_worker(self) -> None:
        helper = DEFAULT_HOME / "computer_use_observer.py"
        result = {"source":"local_codex_computer_use_observer_v1","state":"unavailable"}
        try:
            proc = subprocess.run([sys.executable, str(helper)],
                                  capture_output=True, text=True, check=False, timeout=4.5)
            if proc.returncode == 0:
                parsed = json.loads(proc.stdout)
                if parsed.get("source") == "local_codex_computer_use_observer_v1":
                    result = parsed
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass
        finally:
            with self.computer_use_lock:
                self.computer_use_result = result
                self.computer_use_running = False

    def maybe_begin_computer_use(self) -> None:
        # Independent of proxy ownership and network health. Read-only metadata.
        now = time.monotonic()
        with self.computer_use_lock:
            if self.computer_use_running or now - self.computer_use_last_run < 60:
                return
            self.computer_use_running = True
            self.computer_use_last_run = now
        threading.Thread(target=self._computer_use_worker, daemon=True,
                         name="ComputerUseReadOnlyObserver").start()

    def _deep_probe_worker(self, generation: int, proxy: str) -> None:
        helper=DEFAULT_HOME / "gpt_deep_probe.py"
        outcome={"source":"bounded_public_tls_probes","state":"unavailable"}
        try:
            proc=subprocess.run([sys.executable,str(helper),proxy],
                                capture_output=True,text=True,check=False,timeout=28)
            if proc.returncode==0:
                parsed=json.loads(proc.stdout)
                if parsed.get("source")=="bounded_public_tls_probes":outcome=parsed
        except (OSError,ValueError,TypeError,subprocess.SubprocessError):
            pass
        finally:
            with self.deep_probe_lock:
                if generation == self.route_generation:
                    self.deep_probe_result=outcome
                self.deep_probe_running=False

    def maybe_begin_deep_probe(self, network_healthy: bool) -> None:
        if not self.config.get("deep_connection_probe_enabled",True):
            return
        now=time.monotonic()
        # During a fault we NEED layer evidence. Retain bounded throttling
        # rather than stopping all diagnostics when the public probe fails.
        interval=(max(90,min(180,int(self.config.get("deep_connection_probe_interval_seconds",300))))
                  if not network_healthy else max(180,int(self.config.get("deep_connection_probe_interval_seconds",300))))
        with self.deep_probe_lock:
            if self.deep_probe_running or now-self.deep_probe_last_run<interval:
                return
            self.deep_probe_running=True
            self.deep_probe_last_run=now
        threading.Thread(target=self._deep_probe_worker,
                         args=(self.route_generation,str(self.config["proxy"])),
                         daemon=True,name="GPTAndCodexLayeredReadOnlyProbe").start()

    def _upload_probe_worker(self, proxy: str) -> None:
        helper = DEFAULT_HOME / "upload_probe.py"
        outcome = {"source": "bounded_upload_probe", "state": "unavailable", "kbps": 0.0}
        try:
            proc = subprocess.run(
                [sys.executable, str(helper), proxy,
                 str(self.config.get("upload_probe_url", "https://postman-echo.com/post"))],
                capture_output=True, text=True, check=False, timeout=90)
            if proc.returncode == 0:
                parsed = json.loads(proc.stdout)
                if parsed.get("source") == "bounded_upload_probe":
                    outcome = parsed
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass
        finally:
            with self.upload_probe_lock:
                self.upload_probe_result = outcome
                self.upload_probe_running = False

    def _consume_upload_request(self) -> bool:
        """A menu click drops a one-shot flag file; consume it exactly once."""
        try:
            request = DEFAULT_HOME / "upload_probe.request"
            if request.exists():
                request.unlink()
                return True
        except OSError:
            pass
        return False

    def maybe_begin_upload_probe(self) -> None:
        """Measure real uplink. Bounded, throttled, never a switch trigger."""
        if not self.config.get("upload_probe_enabled", False):
            return
        now = time.monotonic()
        interval = max(300, int(self.config.get("upload_probe_interval_seconds", 900)))
        with self.upload_probe_lock:
            if self.upload_probe_running:
                # Leave a pending manual request in place for the next cycle.
                return
            forced = self._consume_upload_request()
            if not forced and now - self.upload_probe_last_run < interval:
                return
            self.upload_probe_running = True
            self.upload_probe_last_run = now
        threading.Thread(target=self._upload_probe_worker,
                         args=(str(self.config.get("proxy", "")),),
                         daemon=True, name="UploadThroughputProbe").start()

    def _node_name_worker(self) -> None:
        # Protected Group Container: always through a bounded child process.
        helper = DEFAULT_HOME / "shadowrocket_node.py"
        outcome = {"source": "shadowrocket_selected_server", "state": "unavailable", "name": ""}
        try:
            proc = subprocess.run([sys.executable, str(helper)], capture_output=True,
                                  text=True, check=False, timeout=2.5)
            if proc.returncode == 0:
                parsed = json.loads(proc.stdout)
                if parsed.get("source") == "shadowrocket_selected_server":
                    outcome = parsed
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass
        finally:
            with self.node_name_lock:
                self.node_name_result = outcome
                self.node_name_running = False

    def maybe_begin_node_name(self) -> None:
        now = time.monotonic()
        with self.node_name_lock:
            if self.node_name_running or now - self.node_name_last_run < 60:
                return
            self.node_name_running = True
            self.node_name_last_run = now
        threading.Thread(target=self._node_name_worker, daemon=True,
                         name="ShadowrocketNodeNameReader").start()

    def _native_proxy_log_worker(self) -> None:
        # The guard process NEVER opens the protected Shadowrocket directory.
        # A short-lived, time-limited child performs only read-only SQL and
        # emits sanitized per-OpenAI-group node records, no URLs or UA.
        helper = DEFAULT_HOME / "shadowrocket_native_log_probe.py"
        error_kind = "reader_unavailable"
        try:
            process = subprocess.run(
                [sys.executable, str(helper), "--group",
                 str(self.config.get("native_fallback_group", ""))],
                capture_output=True, text=True, check=False, timeout=2.5,
            )
            if process.returncode:
                error_kind = "reader_exit_" + str(int(process.returncode))
                raise ValueError("reader child failed")
            payload = json.loads(process.stdout)
            if payload.get("source") != "shadowrocket_native_proxy_log":
                raise ValueError("unexpected source")
            latest = payload.get("latest")
            if latest is not None and (
                not isinstance(latest, dict) or
                latest.get("group") != self.config.get("native_fallback_group") or
                latest.get("source") != "shadowrocket_native_proxy_log"
            ):
                raise ValueError("unexpected group")
            with self.native_log_lock:
                if latest:
                    old = self.native_log_latest
                    # A prior recorded request is immutable evidence,
                    # but not proof of the route selected *right now*.
                    if (old and latest.get("name") != old.get("name")
                            and int(latest.get("epoch",0)) > int(old.get("epoch",0))):
                        self.native_log_history.append({
                            "observed_at": latest["observed_at"],
                            "from_node": old["name"],
                            "to_node": latest["name"],
                            "source": "shadowrocket_native_proxy_log",
                            "evidence": "different_nodes_in_observed_GPT_requests",
                            "is_fallback_switch_confirmed": False,
                        })
                        self.native_log_history = self.native_log_history[-10:]
                        self.logger.info(
                            "native GPT proxy log observed different nodes in requests"
                        )
                    if (not old or int(latest.get("epoch",0)) >= int(old.get("epoch",0))):
                        self.native_log_latest = latest
                self.native_log_error = ""
        except subprocess.TimeoutExpired:
            with self.native_log_lock:
                self.native_log_error = "reader_timeout"
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as err:
            # Only a failure *category* is exposed; stderr might contain
            # private directory or access context, so never persist it.
            with self.native_log_lock:
                self.native_log_error = (
                    error_kind if error_kind != "reader_unavailable"
                    else "reader_" + type(err).__name__.lower()
                )
            # No sensitive stderr or URL is persisted.
        finally:
            with self.native_log_lock:
                self.native_log_running = False

    def maybe_begin_native_proxy_log(self) -> None:
        if not (self.active_backend == "shadowrocket"
                and self.config.get("native_fallback_enabled", False)
                and self.config.get("native_proxy_log_reader_enabled", False)
                and self.config.get("native_fallback_group")):
            return
        now = time.monotonic()
        with self.native_log_lock:
            if (self.native_log_running or
                now - self.native_log_last_run_at <
                    max(30, int(self.config.get("native_proxy_log_reader_interval_seconds",40)))):
                return
            self.native_log_running = True
            self.native_log_last_run_at = now
        threading.Thread(
            target=self._native_proxy_log_worker,
            daemon=True,
            name="TunnelSentinel-NativeNodeReader",
        ).start()

    def _ai_matrix_runner(self, generation: int | None = None, proxy: str | None = None) -> None:
        if generation is None:
            generation = self.route_generation
        if proxy is None:
            proxy = str(self.config["proxy"])
        # Only public Cloudflare trace endpoints. Every URL is a fixed code
        # constant, never a URL from untrusted HTML, subscription or response.
        def check(site: tuple[str, str]) -> dict:
            name, domain = site
            result = curl_probe("ai-" + domain,
                                "https://" + domain + "/cdn-cgi/trace", proxy)
            ok = (result.transport_ok and result.http_code == 200
                  and bool(result.egress_ip))
            return {
                "name": name, "domain": domain,
                "status": "reachable" if ok else "unverified",
                "http_code": result.http_code,
                "latency_ms": round(result.duration * 1000),
                "egress_country": result.egress_country if ok else "",
                "egress_colo": result.egress_colo if ok else "",
                "egress_ip": result.egress_ip if ok else "",
            }
        try:
            with ThreadPoolExecutor(max_workers=3) as workers:
                checks = list(workers.map(check, AI_TRACE_TARGETS))
            # HEAD is only a speculative compatibility check; the actual
            # Shadowrocket native fallback probe method is NOT yet proven.
            # No extra request unless explicitly enabled, and no dynamic
            # proxy reconfiguration on a challenged or ambiguous result.
            audit = {}
            if self.config.get("endpoint_method_audit_enabled", False):
                route = next((r for r in checks if r["domain"] == "chatgpt.com"), None)
                head = curl_probe(
                    "method-head-current-route",
                    "https://chatgpt.com/cdn-cgi/trace", proxy,
                    http_head=True,
                )
                get_ok = bool(route and route["status"] == "reachable")
                audit = {
                    "get_code": route["http_code"] if route else 0,
                    "head_code": head.http_code,
                    "head_cloudflare_challenge": bool(head.challenged),
                    "result": (
                        "possible_head_false_negative"
                        if get_ok and head.http_code == 403 and head.challenged
                        else "no_mismatch_observed"
                        if get_ok and head.transport_ok and head.http_code == 200
                        else "inconclusive"
                    ),
                    "scope": "current_route_only_not_native_fallback_proof",
                }
            with self.ai_matrix_lock:
                if generation == self.route_generation:
                    self.ai_matrix_checks = checks
                    self.endpoint_method_audit = audit
                    self.ai_matrix_checked_at = time.time()
        except Exception as exc:
            self.logger.warning("AI routing supplemental checks failed: %s",
                                type(exc).__name__)
        finally:
            with self.ai_matrix_lock:
                self.ai_matrix_running = False

    def maybe_begin_ai_matrix(self, network_healthy: bool) -> None:
        if not self.config.get("ai_matrix_enabled", False) or not network_healthy:
            return
        now = time.monotonic()
        interval = max(300, int(self.config.get("ai_matrix_interval_seconds", 900)))
        with self.ai_matrix_lock:
            if self.ai_matrix_running or now - self.ai_matrix_started_at < interval:
                return
            self.ai_matrix_started_at = now
            self.ai_matrix_running = True
        threading.Thread(target=self._ai_matrix_runner,
                         args=(self.route_generation,str(self.config["proxy"])),
                         daemon=True,name="TunnelSentinel-AIRoutingAudit").start()

    def known_good_candidates(self) -> list[str]:
        # Revalidate age at least every 5 minutes while the daemon is running.
        # Do not keep a 72-hour-old node forever in memory during long uptime.
        if time.monotonic() - self.known_good_cache_updated_at > 300:
            self.learned_good_nodes = read_known_good_nodes(
                DEFAULT_LOG_DIR / "guardian.log",
                max_age_hours=float(self.config.get("known_good_max_age_hours", 72)),
            )
            self.known_good_cache_updated_at = time.monotonic()
        # Check supplied names against observed successful names: this prevents
        # stale subscription names from causing useless changes.
        # Only names which really passed the public edge within the recent
        # window are eligible. User configured order is a preference, not proof
        # that a subscription still contains an old server.
        observed = list(dict.fromkeys(self.learned_good_nodes))
        configured = [n for n in self.config.get("nodes", []) if n in observed]
        return configured + [n for n in observed if n not in configured]

    def note_verified_healthy(self) -> None:
        node = self.current_node if self.current_node_verified else None
        if not node:
            self.healthy_streak_count = 0
            self.healthy_streak_node = None
            return
        if node == self.healthy_streak_node:
            self.healthy_streak_count += 1
        else:
            self.healthy_streak_node = node
            self.healthy_streak_count = 1
        if self.healthy_streak_count >= 2 and node not in self.learned_good_nodes:
            self.learned_good_nodes.insert(0, node)
            self.logger.info("historical public-edge HTTP200 observed twice node=%s", node)

    def _load_previous_status(self) -> dict:
        try:
            payload = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def probe_all(self) -> list[ProbeResult]:
        urls = self.config["probe_urls"]
        proxy = self.config["proxy"]
        first = curl_probe("edge", urls["edge"], proxy)
        if first.transport_ok and first.http_code == 200:
            return [first]
        time.sleep(0.5)
        return [curl_probe("edge-retry", urls["edge"], proxy)]

    @staticmethod
    def path_is_healthy(results: list[ProbeResult]) -> bool:
        # Unauthenticated calls to internal ChatGPT endpoints may legitimately
        # receive a Cloudflare challenge even while the signed-in desktop app
        # and image generation work. The public edge probe establishes the
        # proxy/TLS path; real backend and websocket failures come from new
        # desktop-app log entries.
        return any(result.transport_ok and result.http_code == 200 for result in results)

    def observe_egress_change(self, results: list[ProbeResult], healthy: bool) -> None:
        """Observe *outbound IP* changes, not provider node switches.

        The same proxy server may use multiple outgoing IPs. Two consecutive
        healthy samples are required to ignore one-off connection variance.
        """
        sample = next(
            (r for r in results if r.transport_ok and r.http_code == 200 and r.egress_ip), None
        )
        if not healthy or sample is None:
            self.pending_egress = None
            self.pending_egress_count = 0
            return
        current = (sample.egress_ip, sample.egress_country, sample.egress_colo)
        if self.pending_egress == current:
            self.pending_egress_count += 1
        else:
            self.pending_egress = current
            self.pending_egress_count = 1
        if self.pending_egress_count < 2:
            return
        old = self.confirmed_egress
        if old is None:
            self.confirmed_egress = current
        elif current[0] != old[0]:
            recent_outage = (
                self.last_edge_recovered_at > 0
                and time.monotonic() - self.last_edge_recovered_at <= 180
            )
            item = {
                "observed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "egress_before": old[0],
                "egress_after": current[0],
                "geo_before": "-".join(x for x in old[1:] if x),
                "geo_after": "-".join(x for x in current[1:] if x),
                "preceded_by_recent_public_outage": recent_outage,
                "confirmation": "2_consecutive_healthy_probes",
                "evidence": "confirmed_public_edge_egress_change",
                "native_backend_switch_verified": False,
            }
            self.egress_changed_at.append(item)
            self.egress_changed_at = self.egress_changed_at[-6:]
            self.confirmed_egress = current
            self.logger.info(
                "public edge egress changed; 2 healthy probes confirmed; "
                "recent_public_outage=%s; native_backend_switch_verified=false",
                recent_outage,
            )
        else:
            self.confirmed_egress = current

    def observe_edge_incident(self, results: list[ProbeResult], healthy: bool) -> None:
        """Record failure-to-recovery evidence without taking node control."""
        observed = next((r.egress_ip for r in results
                         if r.transport_ok and r.http_code == 200 and r.egress_ip), "")
        now = time.monotonic()
        self.observe_egress_change(results, healthy)
        if not healthy:
            if self.edge_outage_started_at is None:
                self.edge_outage_started_at = now
                self.edge_outage_previous_ip = self.edge_last_healthy_ip
            return
        if self.edge_outage_started_at is not None:
            before = self.edge_outage_previous_ip
            self.last_public_edge_incident = {
                "observed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "sampled_outage_seconds": round(now - self.edge_outage_started_at, 1),
                "egress_before": before,
                "egress_after": observed,
                "egress_changed": bool(before and observed and before != observed),
                "native_backend_switch_verified": False,
                "evidence": "public_edge_probes_only",
            }
            self.logger.warning(
                "public edge reachable again sampled_outage_s=%.1f egress_changed=%s "
                "backend_switch_verified=false",
                self.last_public_edge_incident["sampled_outage_seconds"],
                self.last_public_edge_incident["egress_changed"],
            )
            self.last_edge_recovered_at = now
            self.edge_outage_started_at = None
            self.edge_outage_previous_ip = ""
        if observed:
            self.edge_last_healthy_ip = observed

    def record_failures(self, count: int) -> None:
        now = time.monotonic()
        for _ in range(count):
            self.failure_times.append(now)
        cutoff = now - float(self.config["failure_window_seconds"])
        while self.failure_times and self.failure_times[0] < cutoff:
            self.failure_times.popleft()

    def should_switch(self) -> bool:
        if not self.config.get("automatic_control_enabled",False) or self.active_backend != "shadowrocket":
            return False
        # A native Shadowrocket fallback policy controls actual egress nodes.
        # Never race it with the legacy shadowrocket://select control channel.
        if self.config.get("native_fallback_enabled", False):
            if self.failure_times:
                self.recovery_state = "native_fallback_waiting"
                self.recovery_reason = "由 Shadowrocket 原生 fallback 接管节点切换；持续检测链路"
            return False
        now = time.monotonic()
        if not self.current_node_verified and not self.config.get("dry_run", False):
            self.recovery_state = "node_unverified"
            self.recovery_reason = "无法确认 Shadowrocket 当前节点，禁止盲目切换"
            return False
        if now - self.started_at < float(self.config["startup_grace_seconds"]):
            return False
        if now < self.manual_override_until:
            return False
        if now < self.recovery_retry_at:
            return False
        if now - self.last_switch_at < float(self.config["switch_cooldown_seconds"]):
            return False
        return len(self.failure_times) >= int(self.config["failures_before_switch"])

    def attempt_failover(self) -> bool:
        if not self.config.get("automatic_control_enabled",False):
            self.recovery_state="monitoring"
            self.recovery_reason="只读监控：禁止自动修改节点"
            return False
        original = self.current_node
        nodes = [n for n in self.known_good_candidates() if n != original]
        self.last_switch_at = time.monotonic()
        self.recovery_attempt_count += 1
        self.recovery_state = "attempting"
        self.logger.warning(
            "recovery attempt=%d from=%s eligible_known_good=%d",
            self.recovery_attempt_count, original or "unknown", len(nodes),
        )
        if not nodes:
            self.recovery_state = "no_candidates"
            self.recovery_reason = "没有经过实际健康验证的其他节点；旧配置节点已跳过"
            self.recovery_retry_at = time.monotonic() + float(
                self.config.get("recovery_backoff_seconds", 900))
            self.logger.error("recovery blocked: no verified candidate; no switching requested")
            return False
        # A selector that silently fails should not be retried against every
        # other node: that is a broken *control channel*, not bad proxy nodes.
        node = nodes[0]
        self.logger.warning("trying known-good node=%s", node)
        if not select_shadowrocket_node(node, bool(self.config["dry_run"])):
            self.recovery_state = "selector_unavailable"
            self.recovery_reason = "Shadowrocket 选择指令被拒绝"
        elif not self.config["dry_run"] and not wait_for_shadowrocket_node(
            node, float(self.config["switch_settle_seconds"])
        ):
            self.recovery_state = "selector_unavailable"
            self.recovery_reason = "指令已发送，但 Shadowrocket 未实际切换节点"
        else:
            self.current_node = node
            self.current_node_verified = not self.config["dry_run"]
            results = self.probe_all()
            self.last_probe_results = results
            if self.path_is_healthy(results):
                self.failure_times.clear()
                self.recovery_retry_at = 0.0
                self.recovery_state = "recovered"
                self.recovery_reason = "候选节点已通过最新链路检查"
                self.note_verified_healthy()
                self.logger.warning("recovery verified node=%s", node)
                return True
            self.recovery_state = "candidate_unhealthy"
            self.recovery_reason = "目标已选中，但目标节点未通过链路检查"
            if original and not self.config["dry_run"]:
                select_shadowrocket_node(original, False)
                self.current_node_verified = wait_for_shadowrocket_node(
                    original, float(self.config["switch_settle_seconds"]))
                self.current_node = original

        self.recovery_retry_at = time.monotonic() + float(
            self.config.get("recovery_backoff_seconds", 900))
        self.logger.error("recovery stopped state=%s reason=%s; retry deferred",
                          self.recovery_state, self.recovery_reason)
        return False

    @staticmethod
    def _probe_summary(results: list[ProbeResult]) -> str:
        return ",".join(
            f"{result.name}:{result.http_code}:{'ok' if result.transport_ok else 'bad'}"
            for result in results
        )

    def write_status(
        self,
        results: list[ProbeResult],
        log_failures: int,
        healthy: bool,
        proxy_available: bool = True,
        tunnel_stop_reason: str = "none",
        network_failure_streak: int = 2,
    ) -> None:
        issues = self.log_watcher.issue_summary()
        with self.codex_stream_lock:
            stream_info = dict(self.codex_stream_result)
        counts = stream_info.get("counts") or {}
        # ws_closed_after_upgrade counts a WebSocket that upgraded (101) and then
        # died. It is a display/business signal only; it is deliberately NOT part
        # of clash_error_score, so it can never increase the switch score.
        stream_count = sum(int(counts.get(k,0)) for k in
                           ("broken_pipe","websocket_handshake","connection_reset",
                            "ws_closed_after_upgrade"))
        ws_degraded = (stream_info.get("classification") == "ws_degraded"
                       or int(counts.get("http_fallbacks",0)) > 0)
        last_error = int(stream_info.get("last_at",0))
        # Inform about failed authenticated Codex streaming independently of
        # public edge availability. NEVER increase the automatic switch score.
        if (stream_info.get("state")=="ok" and stream_count and
                0 <= time.time()-last_error <= 1800):
            issues.append({"category":"codex_stream",
                           "title":("Codex WebSocket 传输异常，已回退 HTTP" if ws_degraded
                                    else "Codex 近30分钟响应流中断"),
                           "count":stream_count,"last_seen":last_error})
            issues = sorted(issues,key=lambda x:x["last_seen"],reverse=True)[:6]
        observed = next(
            (result for result in results
             if result.transport_ok and result.http_code == 200 and result.egress_ip),
            None,
        )
        with self.ai_matrix_lock:
            ai_busy = self.ai_matrix_running
            ai_age = (time.time() - self.ai_matrix_checked_at
                      if self.ai_matrix_checked_at else float("inf"))
            max_age = max(600, int(self.config.get("ai_matrix_interval_seconds", 900)) * 2)
            ai_valid = (healthy and self.config.get("ai_matrix_enabled", False)
                        and 0 <= ai_age <= max_age)
            ai_rows = [row.copy() for row in self.ai_matrix_checks] if ai_valid else []
            method_audit = (self.endpoint_method_audit.copy() if ai_valid
                            and self.config.get("endpoint_method_audit_enabled", False) else {})
            ai_when = (datetime.fromtimestamp(self.ai_matrix_checked_at)
                       .astimezone().isoformat(timespec="seconds")
                       if ai_valid else "")
        with self.deep_probe_lock:
            deep=dict(self.deep_probe_result)
            deep_running=self.deep_probe_running
        with self.computer_use_lock:
            computer_use=dict(self.computer_use_result)
        deep_when=int(deep.get("checked_at",0))
        if deep_when<=0 or not (0<=time.time()-deep_when<=max(600,2*int(self.config.get("deep_connection_probe_interval_seconds",300)))):
            deep={"source":"bounded_public_tls_probes","state":"pending_or_stale",
                  "targets":[],"limitations":"no_authenticated_computer_use_test"}
        deep["running"]=deep_running
        with self.upload_probe_lock:
            upload = dict(self.upload_probe_result)
            upload_running = self.upload_probe_running
        upload_when = int(upload.get("at", 0))
        if upload_when <= 0 or not (0 <= time.time() - upload_when
                                    <= max(1800, 3 * int(self.config.get("upload_probe_interval_seconds", 900)))):
            upload = {"source": "bounded_upload_probe", "state": "pending_or_stale", "kbps": 0.0}
        upload["running"] = upload_running
        with self.node_name_lock:
            node_info = dict(self.node_name_result)
        if upload.get("state") == "ok":
            upload["node"] = str(node_info.get("name", "") or "")
        try:
            if (upload.get("state") == "ok" and observed is not None
                    and getattr(observed, "egress_ip", "")):
                upload_history = record_upload_sample(
                    ip=observed.egress_ip,
                    country=observed.egress_country or "",
                    colo=observed.egress_colo or "",
                    kbps=float(upload.get("kbps") or 0),
                    at=int(upload.get("at") or time.time()),
                    node=str(node_info.get("name", "") or ""))
            else:
                upload_history = _load_upload_history()
        except (OSError, ValueError, TypeError):
            upload_history = []
        upload_advice = upload_recommendation(upload_history, upload, observed)
        now=time.time()
        workflow_axes=evaluate_workflow_health(now=now,healthy=healthy,
                         proxy_available=proxy_available,deep=deep,stream=stream_info,
                         issues=issues,computer_use=computer_use,
                         network_failure_streak=network_failure_streak)
        if self.active_backend == "system_unresolved":
            # PAC/auto-discovery cannot be faithfully resolved by reading static
            # scutil values. Unknown != actual failed user connections.
            workflow_axes["network"]={"state":"unknown","label":"系统代理路由尚未解析",
                                      "source":"macos_system_proxy","observed_at":int(now),
                                      "detail":"PAC 或系统代理信息暂不可读"}
            workflow_axes["chatgpt"]={"state":"unknown","label":"未检测当前实际出站路径",
                                      "source":"none","observed_at":0,"detail":""}
        try:
            timeline=update_workflow_timeline(self.status_path.parent / "workflow_timeline.json",
                         now=now, axes=workflow_axes,
                         proxy_client=self.active_backend,
                         stream=stream_info,issues=issues,egress_history=self.egress_changed_at,
                         computer_use=computer_use)
        except (OSError,ValueError,TypeError):
            self.logger.warning("workflow timeline unavailable; monitoring continues")
            timeline={"source":"tunnelsentinel_workflow_evidence_v1","events":[],
                      "active_incident":None,"state":"unavailable"}
        with self.native_log_lock:
            native = self.native_log_latest.copy()
            native_events = [e.copy() for e in self.native_log_history[-10:]]
            native_reader_problem = self.native_log_error
        try:
            native_age = time.time() - int(native.get("epoch",0))
        except (TypeError,ValueError):
            native_age = float("inf")
        native_recent = (
            self.active_backend == "shadowrocket"
            and self.config.get("native_proxy_log_reader_enabled",False)
            and self.config.get("native_fallback_enabled",False)
            and healthy and proxy_available
            and 0 <= native_age <= max(60,int(self.config.get("native_proxy_node_recent_seconds",600)))
            and native.get("group") == self.config.get("native_fallback_group")
        )
        clash_active = self.active_backend == "clash"
        shadowrocket_active = self.active_backend == "shadowrocket"
        system_route = self.system_route_observation
        clash = self.clash_observation if clash_active else {}
        clash_node = str(clash.get("active_request_node", "")) if clash_active else ""
        clash_request_verified = bool(clash_node and int(clash.get("active_gpt_connections",0)) > 0
                                      and clash.get("api_healthy") is True)
        clash_recent_errors = stream_info.get("recent_counts") or {}
        clash_error_score = sum(int(clash_recent_errors.get(k,0)) for k in
                                ("broken_pipe","websocket_handshake","connection_reset"))
        dedicated_ready = clash_active and clash.get("ai_group") == "TunnelSentinel-OpenAI" \
            and clash.get("ai_group_type") == "Selector" and int(clash.get("candidate_count",0)) >= 2
        live_clash_enabled = bool(dedicated_ready and self.config.get("automatic_control_enabled",False)
                                  and self.config.get("clash_auto_failover_enabled",False))
        clash_plan = {
            "mode":"live_guarded" if live_clash_enabled else "offline_simulation_no_write",
            "would_trigger": bool(clash_active and clash_error_score >= 3),
            "eligible_candidates": int(clash.get("eligible_count",0)) if clash_active else 0,
            "candidate_scope": "dedicated_TunnelSentinel_OpenAI" if dedicated_ready else "shared_AI_to_Proxies",
            "blocked_reason":"" if live_clash_enabled else
                 "disabled_by_setting" if dedicated_ready else "dedicated_openai_group_required_before_switch",
            "will_change_routes":bool(live_clash_enabled and clash_error_score >= 3),
            "live_enabled":live_clash_enabled,
        } if clash_active else {}
        payload = {
            "workflow_health": workflow_axes,
            "client_event_correlation": correlate_client_events(stream_info,computer_use,now),
            "computer_use_observation": computer_use,
            "workflow_timeline": timeline,
            "deep_connection_diagnostics": deep,
            "upload_probe": upload,
            "upload_node_history": upload_history,
            "shadowrocket_node": node_info,
            "upload_recommendation": upload_advice,
            "automatic_control_enabled": bool(self.config.get("automatic_control_enabled",False)),
            "tunnel_recovery_enabled": bool(self.config.get("tunnel_recovery_enabled",False)),
            "proxy_client": self.active_backend,
            "system_proxy_source": system_route.get("source","unverified"),
            "system_proxy_state": system_route.get("state","legacy_configured"),
            "system_proxy_endpoint": system_route.get("endpoint",""),
            "system_proxy_type": system_route.get("proxy_type",""),
            "monitor_proxy_url": (str(self.config.get("proxy",""))
                                  if self.active_backend != "system_unresolved" else ""),
            "configured_native_fallback_group": str(self.config.get("native_fallback_group","")),
            "native_group_route_verified": False,
            "proxy_control_mode": ("automatic" if self.config.get("automatic_control_enabled",False)
                                   else "read_only"),
            "clash_failover_plan": clash_plan,
            "clash_failover_status": (lambda x: x if x else {})(self._load_clash_failover_status()) if clash_active else {},
            "clash_observation": {k:clash.get(k) for k in
                ("source","observed_at","active","api_healthy","mode","tun_enabled",
                 "ai_group","ai_group_type","ai_selection","child_group_type",
                 "selected_node","active_request_node","active_request_chain",
                 "active_gpt_connections","candidate_count","eligible_count",
                 "dry_run_candidate","switch_simulation","reason") if k in clash},
            "clash_auto_switch_mode": "live_guarded" if live_clash_enabled else "simulation_only" if clash_active else "not_applicable",
            "codex_stream_diagnostics": stream_info,
            "codex_stream_sqlite_monitor_enabled": bool(self.config.get("codex_stream_sqlite_monitor_enabled",False)),
            "native_proxy_log_reader_enabled": bool(self.config.get("native_proxy_log_reader_enabled",False)),
            "native_proxy_log_recent": bool(native_recent),
            "native_proxy_log_read_status": native_reader_problem or "ok",
            # Old Shadowrocket native-log evidence is historical, never the
            # current per-request identity of an unrelated proxy client.
            "native_proxy_last_connection": native if shadowrocket_active else {},
            "native_proxy_node_history": native_events if shadowrocket_active else [],
            "native_proxy_node_scope": "per-request name from native log, not continuous backend state",
            "ai_matrix_enabled": bool(self.config.get("ai_matrix_enabled", False)),
            "ai_matrix_source": "local_public_trace_requests",
            "ai_matrix_checked_at": ai_when,
            "ai_matrix_running": ai_busy,
            "ai_matrix_fresh": bool(ai_valid),
            "ai_matrix_sites": ai_rows,
            "endpoint_method_audit": method_audit,
            "endpoint_method_audit_limit": "Observed route only; not a Shadowrocket backend-method trace",
            "ai_matrix_limit": "Public access/routing only; not node unlock or authenticated chat",
            "version": VERSION,
            "pid": os.getpid(),
            # These are semantic summaries of independent evidence axes;
            # an HTTP 200 cannot become "GPT business healthy".
            "overall_status": (
                "offline" if workflow_axes["network"]["state"] == "failed"
                else "unknown" if workflow_axes["network"]["state"] == "unknown"
                else "verifying" if workflow_axes["network"]["state"] == "partial"
                else "attention" if issues or any(
                    workflow_axes[k]["state"]=="degraded" for k in ("codex","computer_use"))
                else "reachable"
            ),
            "business_status": (
                "attention" if issues or any(
                    workflow_axes[k]["state"]=="degraded" for k in ("codex","computer_use"))
                else "client_metadata_only" if workflow_axes["codex"]["state"]=="partial"
                else "unverified"
            ),
            "business_evidence_scope": "no_authenticated_ChatGPT_or_Computer_Use_completion_proof",
            "public_edge_failure_streak": network_failure_streak if not healthy else 0,
            "route_management": (
                "clash_observe_only" if clash_active else
                "shadowrocket_policy_unverified" if shadowrocket_active and self.config.get("native_fallback_enabled",False)
                else "shadowrocket_global_monitor" if shadowrocket_active else
                "system_proxy_observe_only"),
            "native_fallback_group": str(self.config.get("native_fallback_group", "")),
            # An observation is valid only for THIS probe cycle. In
            # particular, do not leak a cached IP into failure/stale states.
            "openai_egress_observed": bool(observed and healthy),
            "openai_egress_ip": observed.egress_ip if observed and healthy else "",
            "openai_egress_colo": observed.egress_colo if observed and healthy else "",
            "openai_egress_country": observed.egress_country if observed and healthy else "",
            "openai_egress_source": "chatgpt_public_edge" if observed and healthy else "unverified",
            "openai_group_backend_name": clash_node if clash_active else str(native.get("name","")) if native_recent else "",
            "openai_group_backend_verified": clash_request_verified if clash_active else bool(native_recent),
            "openai_group_backend_observed_at": (datetime.fromtimestamp(int(clash.get("observed_at",0))).astimezone().isoformat(timespec="seconds")
                                                 if clash_request_verified else native.get("observed_at","") if native and not clash_active else ""),
            "openai_group_backend_source": ("mihomo_active_connections" if clash_request_verified else "unverified") if clash_active
                                         else "shadowrocket_native_proxy_log" if native_recent else "unverified",
            "current_node_scope": (
                "clash_selected_group" if clash_active else
                "shadowrocket_global_selection" if shadowrocket_active and self.config.get("native_fallback_enabled",False)
                else "shadowrocket_selected_server" if shadowrocket_active
                else "system_proxy_endpoint_only"),
            "recovery_state": self.recovery_state,
            "recovery_reason": self.recovery_reason,
            "recovery_attempt_count": self.recovery_attempt_count,
            "recovery_retry_seconds": max(0, round(self.recovery_retry_at - time.monotonic())),
            # Back-compat: historical probe passes, never "GPT-good" servers.
            "known_good_candidates": self.known_good_candidates()[:12],
            "historical_public_edge_nodes": self.known_good_candidates()[:12],
            "known_good_candidates_scope": "historical_global_selection_public_trace_http200_only_not_GPT_business_or_current_subscription",
            "business_issues": issues,
            "issue_window_seconds": ISSUE_WINDOW_SECONDS,
            "last_public_edge_incident": self.last_public_edge_incident,
            "egress_change_history": self.egress_changed_at[-6:],
            "egress_history_scope": "2 healthy samples; outbound IP only, not confirmed server change",
            "public_edge_outage_pending": self.edge_outage_started_at is not None,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "healthy": healthy,
            "current_node": clash.get("selected_node", "") if clash_active else self.current_node if shadowrocket_active else "",
            "current_node_verified": (bool(clash.get("selected_node") and clash.get("api_healthy") is True)
                                      if clash_active else self.current_node_verified if shadowrocket_active else False),
            "recent_failure_score": len(self.failure_times),
            "new_log_failures": log_failures,
            "last_switch_monotonic": self.last_switch_at,
            "proxy_available": proxy_available,
            "tunnel_state": ("manual_pause" if self.manual_pause and shadowrocket_active else
                             "running" if proxy_available else "unverified" if self.active_backend == "system_unresolved" else "down"),
            "tunnel_stop_reason": tunnel_stop_reason,
            "manual_pause": self.manual_pause,
            "last_tunnel_reconnect_monotonic": self.last_tunnel_reconnect_at,
            "dry_run": bool(self.config["dry_run"]),
            "probes": [dataclasses.asdict(result) for result in results],
        }
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.status_path)

    def recover_missing_tunnel(self) -> tuple[bool, list[ProbeResult]]:
        now = time.monotonic()
        cooldown = float(self.config["tunnel_reconnect_cooldown_seconds"])
        if now - self.last_tunnel_reconnect_at < cooldown:
            return False, []
        self.last_tunnel_reconnect_at = now
        self.logger.warning("Shadowrocket tunnel is down; requesting reconnect")
        if not connect_shadowrocket_tunnel(bool(self.config["dry_run"])):
            self.logger.error("Shadowrocket connect URL scheme failed")
            return False, []
        time.sleep(float(self.config["tunnel_reconnect_settle_seconds"]))
        if not proxy_endpoint_available(self.config["proxy"]):
            self.logger.error("Shadowrocket tunnel reconnect did not restore proxy listener")
            return False, []
        results = self.probe_all()
        healthy = self.path_is_healthy(results)
        if healthy:
            self.failure_times.clear()
            self.manual_pause = False
            self.logger.warning("Shadowrocket tunnel reconnect succeeded")
        else:
            self.logger.error(
                "Shadowrocket tunnel listener returned but health probe failed probes=%s",
                self._probe_summary(results),
            )
        return healthy, results

    def _load_clash_failover_status(self) -> dict:
        try:
            report = json.loads((DEFAULT_HOME / "clash_failover_status.json").read_text())
            return report if isinstance(report,dict) and 0<=time.time()-int(report.get("checked_at",0))<=1800 else {}
        except (OSError,ValueError,TypeError):
            return {}

    def maybe_clash_failover(self) -> None:
        """One bounded real switch attempt. Only a dedicated GPT group is writable."""
        if (self.active_backend != "clash" or not self.config.get("automatic_control_enabled",False)
            or not self.config.get("clash_auto_failover_enabled",False)):
            return
        helper=DEFAULT_HOME / "clash_failover.py"
        if not helper.is_file():
            self.logger.warning("clash failover helper is missing; leaving routing unchanged")
            return
        try:
            r=subprocess.run([sys.executable,str(helper)],capture_output=True,text=True,
                             timeout=35,check=False)
            if r.stdout:
                outcome=json.loads(r.stdout)
                state=str(outcome.get("state","unknown"))
                if state not in ("armed","cooldown_or_daily_limit"):
                    self.logger.info("clash_failover state=%s changed=%s",state,
                                     bool(outcome.get("changed")))
        except (OSError,ValueError,subprocess.SubprocessError):
            self.logger.warning("clash failover helper failed safely; no retry storm")

    def _inspect_system_route(self) -> dict:
        helper = DEFAULT_HOME / "system_proxy_observer.py"
        if not helper.is_file():
            # Source checkout paths remain usable in standalone tests, but the
            # production installer must deploy the exact same helper.
            helper = Path(__file__).resolve().parent / "scripts/system_proxy_observer.py"
        try:
            result = subprocess.run([sys.executable,str(helper)],capture_output=True,text=True,
                                    check=False,timeout=5)
            parsed=json.loads(result.stdout) if result.returncode==0 else {}
            if parsed.get("source")=="macos_system_proxy":
                return parsed
        except (OSError,ValueError,TypeError,subprocess.SubprocessError):
            pass
        return {"source":"macos_system_proxy","state":"unavailable","proxy_url":""}

    def _inspect_mihomo(self) -> dict:
        helper=DEFAULT_HOME / "clash_observer.py"
        if not helper.is_file():
            return {}
        try:
            arguments=[sys.executable,str(helper)]
            # Only an explicitly configured local socket is passed to the
            # optional adapter; no private folder scan or public TCP API.
            socket_path=self.config.get("mihomo_socket_path","")
            if isinstance(socket_path,str) and socket_path:
                arguments += ["--socket",socket_path]
            proc=subprocess.run(arguments,capture_output=True,
                                text=True,check=False,timeout=6)
            observation=json.loads(proc.stdout) if proc.returncode==0 else {}
            return observation if observation.get("source")=="mihomo_unix_readonly" else {}
        except (ValueError,OSError,TypeError,subprocess.SubprocessError):
            return {}

    def refresh_active_backend(self) -> None:
        """Choose probe transport from the *current* macOS system route.

        A proxy app is NOT detected by its historical port or a subscription's
        label. Mihomo's API is trusted only when it independently confirms
        ownership of that macOS system-proxy port. All other providers are
        treated as generic system proxies, with no node control/recovery.
        """
        if not self.config.get("proxy_backend_auto_detect_enabled",False):
            return
        route=self._inspect_system_route()
        state=route.get("state")
        selected=str(route.get("proxy_url","")) if state=="explicit" else ""
        if state=="explicit":
            # The current listener executable is the authority, not any
            # historic hardcoded/configured port or a subscription name.
            shadow_owner = route.get("listener_owner") == "shadowrocket"
            if shadow_owner:
                backend="shadowrocket"
                selection=selected
                clash={}
                self.verified_shadowrocket_endpoint=selected
                self.verified_shadowrocket_at=time.monotonic()
                self.missing_tunnel_reconnect_used=False
            elif (route.get("listener_owner")=="missing"
                  and self.config.get("tunnel_recovery_enabled",False)
                  and not self.missing_tunnel_reconnect_used
                  and self.verified_shadowrocket_endpoint==selected
                  and 0 <= time.monotonic()-self.verified_shadowrocket_at <= 90):
                # Recovery CANDIDATE, not vendor ownership proof. Requires an
                # independent fresh OS failure event and live app check below.
                backend="shadowrocket_recovery_candidate"
                selection=selected
                clash={}
            else:
                # A different listener, changed endpoint, or unresolved owner
                # must invalidate the prior proof. Do not restart old apps.
                if (route.get("listener_owner") != "missing" or
                        self.verified_shadowrocket_endpoint != selected):
                    self.verified_shadowrocket_endpoint=""
                    self.verified_shadowrocket_at=0.0

                # Probe the existing official controller in read-only mode; it
                # must confirm current system endpoint ownership to qualify.
                clash=self._inspect_mihomo()
                if (clash.get("active") is True
                    and clash.get("proxy_url")==selected
                    and clash.get("api_healthy") is True):
                    backend="clash"
                    selection=selected
                else:
                    backend="system_proxy"
                    selection=selected
                    clash={}
        elif state=="direct_or_tun":
            self.verified_shadowrocket_endpoint=""
            self.verified_shadowrocket_at=0.0
            backend="system_route"
            selection=""
            clash={}
        else:
            self.verified_shadowrocket_endpoint=""
            self.verified_shadowrocket_at=0.0
            backend="system_unresolved"
            selection=""
            clash={}
        old=(self.active_backend,str(self.config.get("proxy","")))
        new=(backend,selection)
        self.system_route_observation=route
        self.active_backend=backend
        self.config["proxy"]=selection
        self.clash_observation=clash
        if old!=new:
            self.logger.info("system-proxy route changed backend=%s endpoint=%s",
                             backend,route.get("endpoint","none"))
            self.route_generation+=1
            self.failure_times.clear()
            self.consecutive_public_failures=0
            self.manual_pause=False
            self.current_node=None
            self.current_node_verified=False
            self.recovery_state="monitoring"
            self.recovery_reason=""
            with self.deep_probe_lock:
                self.deep_probe_result={}
                self.deep_probe_last_run=0
            with self.ai_matrix_lock:
                self.ai_matrix_checks=[]
                self.ai_matrix_checked_at=0
            self.pending_egress=None
            self.pending_egress_count=0
            self.confirmed_egress=None

    def recover_verified_missing_shadowrocket(self) -> bool:
        """Attempt at most one safe reconnect after freshly proven ownership.

        Being on a former vendor PORT is insufficient. Missing and unreadable
        listeners are different. A manual/unknown stop never restarts an app.
        """
        expected = self.verified_shadowrocket_endpoint
        now = time.monotonic()
        # Only the current process can hold this short-lived ownership lease.
        if (self.active_backend != "shadowrocket_recovery_candidate" or
                not self.config.get("tunnel_recovery_enabled",False) or
                self.missing_tunnel_reconnect_used or not expected or
                self.config.get("proxy","") != expected or
                not 0 <= now - self.verified_shadowrocket_at <= 90):
            return False
        # Re-read current system routing immediately before touching any app.
        fresh = self._inspect_system_route()
        if (fresh.get("state") != "explicit" or
                fresh.get("proxy_url") != expected or
                fresh.get("listener_owner") != "missing"):
            self.recovery_state="recovery_owner_changed"
            self.recovery_reason="监听地址或所有者已变化，取消专属恢复"
            return False
        reason = latest_shadowrocket_stop_reason(min(90,int(self.config.get("tunnel_event_lookback_seconds",300))))
        if reason != "failed" or not shadowrocket_app_still_running():
            self.recovery_state="recovery_not_authorized"
            self.recovery_reason="没有明确的隧道意外失败及原应用运行证据；未自动重连"
            return False
        self.missing_tunnel_reconnect_used=True  # consume before the action
        success, results = self.recover_missing_tunnel()
        # A different client may acquire the listener while we are settling.
        self.refresh_active_backend()
        proven = success and self.active_backend == "shadowrocket"
        self.recovery_state="tunnel_reconnected" if proven else "recovery_unverified"
        self.recovery_reason=("原应用端口恢复且公开测试可达" if proven
                              else "重连结果未能确认原应用监听进程及出口")
        self.observe_edge_incident(results,proven)
        self.write_status(results or [ProbeResult("proxy",False,0,False,0.0,"not verified")],
                          0,proven,proxy_available=proven,
                          tunnel_stop_reason="failed")
        return proven

    def cycle(self) -> bool:
        if not self.config.get("enabled", True):
            self.logger.info("guardian disabled by configuration")
            return True
        self.refresh_active_backend()
        self.maybe_begin_computer_use()
        if self.active_backend == "shadowrocket_recovery_candidate":
            ok = self.recover_verified_missing_shadowrocket()
            if not ok:
                # Never claim the old vendor still owns the system route.
                self.write_status([ProbeResult("proxy",False,0,False,0.0,"listener missing")],
                                  0,False,proxy_available=False,
                                  tunnel_stop_reason="unverified")
            return ok
        # Clash still listening is not proof it owns the current system path.
        # Fail closed if ownership can no longer be established from scutil.
        if self.active_backend == "clash" and self.clash_observation.get("active") is not True:
            self.recovery_state = "backend_unverified"
            self.recovery_reason = "系统代理不再确认属于 Clash；未触发其他代理恢复"
            self.write_status([ProbeResult("proxy_owner",False,0,False,0.0,"unverified")],
                              0,False,proxy_available=False,tunnel_stop_reason="backend_unverified")
            return False
        # P1: no periodic CFPreferences/App Group reads from other clients.
        # Node names must come from opt-in request-level adapter evidence.
        observed_node = None
        self.current_node_verified = observed_node is not None
        if observed_node:
            if self.current_node and observed_node != self.current_node:
                self.logger.info("manual or external node change observed node=%s", observed_node)
                self.failure_times.clear()
                self.manual_override_until = time.monotonic() + float(
                    self.config.get("manual_change_grace_seconds", 90))
                self.recovery_state = "validating"
                self.recovery_reason = "发现节点变化，等待新节点验证"
            self.current_node = observed_node
        proxy_available = (True if self.active_backend == "system_route"
                           else False if self.active_backend == "system_unresolved"
                           else proxy_endpoint_available(self.config["proxy"]))
        if not proxy_available:
            self.maybe_begin_deep_probe(False)
            self.maybe_begin_codex_stream()
            self.maybe_begin_upload_probe()
            self.maybe_begin_node_name()
        tunnel_stop_reason = "none"
        if not proxy_available and self.active_backend in ("clash","system_proxy","system_unresolved"):
            # Never launch Shadowrocket to 'repair' an absent Clash listener.
            self.recovery_state = "backend_unverified" if self.active_backend=="system_unresolved" else "proxy_unavailable"
            self.recovery_reason = "无法确定系统代理出站路径" if self.active_backend=="system_unresolved" else "当前系统代理监听不可达；未启动其他代理"
            self.failure_times.clear()
            self.write_status([ProbeResult("proxy",False,0,False,0.0,self.recovery_reason)],
                              0,False,proxy_available=False,tunnel_stop_reason=self.recovery_state)
            return False
        if not proxy_available:
            tunnel_stop_reason = latest_shadowrocket_stop_reason(
                int(self.config["tunnel_event_lookback_seconds"])
            )
            if tunnel_stop_reason == "manual":
                if not self.manual_pause:
                    self.logger.warning("Shadowrocket tunnel manually stopped; automatic recovery paused")
                self.manual_pause = True
            elif tunnel_stop_reason == "failed":
                self.manual_pause = False

            if self.manual_pause:
                results = [ProbeResult("proxy", False, 0, False, 0.0, "manually paused")]
                self.edge_outage_started_at = None  # Intentional disconnect is not a failover incident.
                self.edge_outage_previous_ip = ""
                self.failure_times.clear()
                self.write_status(
                    results,
                    0,
                    False,
                    proxy_available=False,
                    tunnel_stop_reason=tunnel_stop_reason,
                )
                self.logger.info("tunnel=manual-pause; automatic recovery suppressed")
                return True

            results: list[ProbeResult] = []
            healthy = False
            if self.config.get("tunnel_recovery_enabled", True):
                healthy, results = self.recover_missing_tunnel()
                proxy_available = (True if self.active_backend == "system_route"
                           else False if self.active_backend == "system_unresolved"
                           else proxy_endpoint_available(self.config["proxy"]))
            if healthy:
                self.consecutive_public_failures = 0
                self.observe_edge_incident(results, True)
                self.write_status(
                    results,
                    0,
                    True,
                    proxy_available=proxy_available,
                    tunnel_stop_reason=tunnel_stop_reason,
                )
                return True
            if not results:
                results = [ProbeResult("proxy", False, 0, False, 0.0, "listener unavailable")]
            self.observe_edge_incident(results, False)
            self.record_failures(1)
            self.write_status(
                results,
                0,
                False,
                proxy_available=proxy_available,
                tunnel_stop_reason=tunnel_stop_reason,
            )
            self.logger.info(
                "health=bad tunnel=down score=%d stop_reason=%s",
                len(self.failure_times),
                tunnel_stop_reason,
            )
            return False

        if self.manual_pause:
            self.logger.info("Shadowrocket tunnel is running again; clearing manual pause")
            self.manual_pause = False
        results = self.probe_all()
        healthy = self.path_is_healthy(results)
        self.observe_edge_incident(results, healthy)
        self.maybe_begin_ai_matrix(healthy)
        self.maybe_begin_deep_probe(healthy)
        self.maybe_begin_upload_probe()
        self.maybe_begin_node_name()
        self.maybe_begin_native_proxy_log()
        self.maybe_begin_codex_stream()
        log_failures = self.log_watcher.read_new_failures()
        if log_failures:
            self.logger.warning("new ChatGPT network log failures=%d", len(log_failures))
        # Desktop errors are displayed, but cannot independently rotate a
        # healthy proxy. Bad probes are debounced in the fast-check loop.
        if healthy:
            self.consecutive_public_failures = 0
            self.failure_times.clear()
            self.note_verified_healthy()
            # A healthy probe is not proof that any node was switched or recovered.
            self.recovery_state = "monitoring"
            self.recovery_reason = ""
        else:
            self.consecutive_public_failures = min(100, self.consecutive_public_failures+1)
            self.record_failures(1)
            if self.recovery_state not in ("selector_unavailable","no_candidates",
                                           "candidate_unhealthy"):
                self.recovery_state = "degraded"
        switch_required = self.active_backend == "shadowrocket" and self.should_switch()
        self.write_status(
            results,
            len(log_failures),
            healthy,
            proxy_available=True,
            tunnel_stop_reason=tunnel_stop_reason,
            network_failure_streak=self.consecutive_public_failures,
        )
        self.logger.info(
            "health=%s node=%s score=%d probes=%s",
            "ok" if healthy else "bad",
            (self.clash_observation.get("selected_node", "unknown") if self.active_backend == "clash"
             else self.current_node or "unknown"),
            len(self.failure_times),
            self._probe_summary(results),
        )
        if self.active_backend == "clash":
            self.maybe_clash_failover()
        if switch_required:
            recovered = self.attempt_failover()
            self.write_status(
                self.last_probe_results if recovered else results,
                len(log_failures), recovered, proxy_available=True,
                tunnel_stop_reason=tunnel_stop_reason,
                network_failure_streak=self.consecutive_public_failures if not recovered else 0,
            )
            return recovered
        return healthy

    def run(self) -> int:
        while not self.stop_requested:
            try:
                self.cycle()
            except Exception:
                self.logger.exception("guardian cycle failed")
            checking_fast = bool(self.failure_times) or self.recovery_state in (
                "degraded", "validating", "selector_unavailable",
                "no_candidates", "candidate_unhealthy"
            )
            interval = self.config.get("fast_check_interval_seconds", 10) if checking_fast else self.config["check_interval_seconds"]
            deadline = time.monotonic() + max(3.0, float(interval))
            while not self.stop_requested and time.monotonic() < deadline:
                if self.refresh_requested:
                    self.refresh_requested = False
                    break
                time.sleep(max(0.0, min(1.0, deadline - time.monotonic())))
        self.logger.info("guardian stopped")
        return 0


def acquire_lock(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    handle = (home / "guardian.lock").open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("OpenAI Link Guardian is already running")
    return handle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--once", action="store_true", help="run one health cycle")
    parser.add_argument("--dry-run", action="store_true", help="never switch a node")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.dry_run:
        config["dry_run"] = True
    home = args.config.parent
    logger = setup_logging(DEFAULT_LOG_DIR, args.verbose)
    lock_handle = acquire_lock(home)
    guardian = Guardian(config, logger, home / "status.json")

    def stop(_signum, _frame):
        guardian.stop_requested = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGUSR1, lambda _signal, _frame: setattr(guardian, "refresh_requested", True))
    logger.info("guardian started version=%s dry_run=%s", VERSION, bool(config["dry_run"]))
    try:
        if args.once:
            healthy = guardian.cycle()
            return 0 if healthy else 2
        return guardian.run()
    finally:
        lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
