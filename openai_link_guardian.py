#!/usr/bin/env python3
"""Keep ChatGPT's Shadowrocket path healthy without using account credentials."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Deque, Iterable, Optional
from urllib.parse import urlencode, urlparse


APP_NAME = "OpenAILinkGuardian"
VERSION = "1.1.0"
DEFAULT_HOME = Path.home() / "Library" / "Application Support" / APP_NAME
DEFAULT_CONFIG = DEFAULT_HOME / "config.json"
DEFAULT_STATUS = DEFAULT_HOME / "status.json"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / APP_NAME
CODEX_LOG_ROOT = Path.home() / "Library" / "Logs" / "com.openai.codex"

DEFAULTS = {
    "enabled": True,
    "dry_run": False,
    "proxy": "http://127.0.0.1:1082",
    "check_interval_seconds": 30,
    "startup_grace_seconds": 45,
    "failure_window_seconds": 150,
    "failures_before_switch": 3,
    "switch_cooldown_seconds": 300,
    "switch_settle_seconds": 3,
    "tunnel_recovery_enabled": True,
    "tunnel_event_lookback_seconds": 300,
    "tunnel_reconnect_cooldown_seconds": 60,
    "tunnel_reconnect_settle_seconds": 3,
    "nodes": [
        "日本2｜解锁流媒体",
        "新加坡1｜流媒体解锁",
        "新加坡2｜流媒体解锁",
        "德国",
        "加拿大",
    ],
    "initial_node": "日本2｜解锁流媒体",
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
    "ERR_TUNNEL_CONNECTION_FAILED",
)


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    name: str
    transport_ok: bool
    http_code: int
    challenged: bool
    duration: float
    detail: str = ""


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


def curl_probe(name: str, url: str, proxy: str, websocket: bool = False) -> ProbeResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="openai-link-guardian-") as temp_dir:
        headers_path = Path(temp_dir) / "headers"
        body_path = Path(temp_dir) / "body"
        command = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--proxy",
            proxy,
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
    return ProbeResult(
        name=name,
        transport_ok=transport_ok,
        http_code=http_code,
        challenged=challenged,
        duration=time.monotonic() - started,
        detail=detail,
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
        # applied the URL action. The subsequent network probe is authoritative.
        return True


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


class LogWatcher:
    def __init__(self, root: Path):
        self.root = root
        self.offsets: dict[str, int] = {}
        self.initialized = False

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

    def read_new_failures(self) -> list[str]:
        failures: list[str] = []
        files = list(self._files())
        if not self.initialized:
            for path in files:
                try:
                    self.offsets[str(path)] = path.stat().st_size
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
                        if self._is_actionable(line):
                            failures.append(line.strip()[:500])
                    self.offsets[key] = handle.tell()
            except OSError:
                continue
        active = {str(path) for path in files}
        self.offsets = {path: offset for path, offset in self.offsets.items() if path in active}
        return failures


class Guardian:
    def __init__(self, config: dict, logger: logging.Logger, status_path: Path):
        self.config = config
        self.logger = logger
        self.status_path = status_path
        self.log_watcher = LogWatcher(CODEX_LOG_ROOT)
        self.failure_times: Deque[float] = collections.deque()
        self.last_switch_at = 0.0
        self.last_tunnel_reconnect_at = 0.0
        self.started_at = time.monotonic()
        self.stop_requested = False
        previous_status = self._load_previous_status()
        self.manual_pause = bool(previous_status.get("manual_pause", False))
        nodes = list(config.get("nodes", []))
        previous_node = previous_status.get("current_node")
        self.current_node = (
            previous_node
            if previous_node in nodes
            else config.get("initial_node") or (nodes[0] if nodes else None)
        )

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

    def record_failures(self, count: int) -> None:
        now = time.monotonic()
        for _ in range(count):
            self.failure_times.append(now)
        cutoff = now - float(self.config["failure_window_seconds"])
        while self.failure_times and self.failure_times[0] < cutoff:
            self.failure_times.popleft()

    def should_switch(self) -> bool:
        now = time.monotonic()
        if now - self.started_at < float(self.config["startup_grace_seconds"]):
            return False
        if now - self.last_switch_at < float(self.config["switch_cooldown_seconds"]):
            return False
        return len(self.failure_times) >= int(self.config["failures_before_switch"])

    def attempt_failover(self) -> bool:
        original = self.current_node
        nodes = list(self.config["nodes"])
        self.logger.warning("failover triggered current_node=%s", original or "unknown")
        for node in ordered_candidates(nodes, original):
            self.logger.warning("trying node=%s", node)
            if not select_shadowrocket_node(node, bool(self.config["dry_run"])):
                self.logger.error("Shadowrocket URL scheme failed node=%s", node)
                continue
            time.sleep(float(self.config["switch_settle_seconds"]))
            results = self.probe_all()
            if self.path_is_healthy(results):
                self.current_node = node
                self.last_switch_at = time.monotonic()
                self.failure_times.clear()
                self.logger.warning("failover succeeded node=%s", node)
                return True
            self.logger.warning("node verification failed node=%s probes=%s", node, self._probe_summary(results))
        if original and original in nodes and not self.config["dry_run"]:
            select_shadowrocket_node(original, False)
            self.logger.error("all candidates failed; requested rollback node=%s", original)
        self.last_switch_at = time.monotonic()
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
    ) -> None:
        payload = {
            "version": VERSION,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "healthy": healthy,
            "current_node": self.current_node,
            "recent_failure_score": len(self.failure_times),
            "new_log_failures": log_failures,
            "last_switch_monotonic": self.last_switch_at,
            "proxy_available": proxy_available,
            "tunnel_state": "manual_pause" if self.manual_pause else ("running" if proxy_available else "down"),
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

    def cycle(self) -> bool:
        if not self.config.get("enabled", True):
            self.logger.info("guardian disabled by configuration")
            return True
        proxy_available = proxy_endpoint_available(self.config["proxy"])
        tunnel_stop_reason = "none"
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
                proxy_available = proxy_endpoint_available(self.config["proxy"])
            if healthy:
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
        log_failures = self.log_watcher.read_new_failures()
        failure_weight = 0 if healthy else 1
        if log_failures:
            failure_weight += min(2, len(log_failures))
            self.logger.warning("new ChatGPT network log failures=%d", len(log_failures))
        self.record_failures(failure_weight)
        self.write_status(
            results,
            len(log_failures),
            healthy,
            proxy_available=True,
            tunnel_stop_reason=tunnel_stop_reason,
        )
        self.logger.info(
            "health=%s node=%s score=%d probes=%s",
            "ok" if healthy else "bad",
            self.current_node or "unknown",
            len(self.failure_times),
            self._probe_summary(results),
        )
        if self.should_switch():
            return self.attempt_failover()
        return healthy

    def run(self) -> int:
        while not self.stop_requested:
            try:
                self.cycle()
            except Exception:
                self.logger.exception("guardian cycle failed")
            deadline = time.monotonic() + float(self.config["check_interval_seconds"])
            while not self.stop_requested and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
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
