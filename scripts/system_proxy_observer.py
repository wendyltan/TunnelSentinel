#!/usr/bin/env python3
"""Observe macOS' CURRENT HTTPS proxy route without touching proxy settings.

No app-name guessing, remote-node inference, preference-file reads, or mutation.
Only sanitized macOS system proxy settings are accepted; never accept a proxy
URL supplied by a web response, subscription, or untrusted input.
"""
from __future__ import annotations

import ipaddress
import json
import re
import subprocess


def _host(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 253 or any(ch in value for ch in "/:@?#\\ \t\r\n"):
        return ""
    bare = value.strip("[]")
    try:
        ipaddress.ip_address(bare)
        return f"[{bare}]" if ":" in bare else bare
    except ValueError:
        return value if re.fullmatch(r"(?i)[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", value) else ""


def parse_scutil(text: str) -> dict:
    entries = dict(re.findall(r"^\s*(HTTPEnable|HTTPProxy|HTTPPort|HTTPSEnable|HTTPSProxy|HTTPSPort|"
                              r"SOCKSEnable|SOCKSProxy|SOCKSPort|ProxyAutoConfigEnable|"
                              r"ProxyAutoConfigURLString|ProxyAutoDiscoveryEnable)\s*:\s*([^\r\n]+)",
                              text, re.M))
    try:
        # A per-host PAC choice cannot be inferred from the static scutil data.
        if entries.get("ProxyAutoConfigEnable") == "1" or entries.get("ProxyAutoDiscoveryEnable") == "1":
            return {"source": "macos_system_proxy", "state": "pac_unresolved",
                    "proxy_client": "system_proxy", "proxy_url": "", "scope": "pac_requires_target_resolution"}
        for prefix, scheme in (("HTTPS", "http"), ("HTTP", "http"), ("SOCKS", "socks5h")):
            if entries.get(f"{prefix}Enable") != "1":
                continue
            host = _host(entries.get(f"{prefix}Proxy", ""))
            port = int(entries.get(f"{prefix}Port", "0"))
            if not host or not 1 <= port <= 65535:
                return {"source": "macos_system_proxy", "state": "invalid",
                        "proxy_client": "system_proxy", "proxy_url": ""}
            return {"source": "macos_system_proxy", "state": "explicit",
                    "proxy_client": "system_proxy", "proxy_url": f"{scheme}://{host}:{port}",
                    "proxy_type": prefix.lower(),
                    "endpoint": f"{host}:{port}",
                    "scope": "macos_current_https_proxy_not_upstream_provider_identity"}
        return {"source": "macos_system_proxy", "state": "direct_or_tun",
                "proxy_client": "system_route", "proxy_url": "",
                "scope": "no_explicit_proxy_may_be_direct_or_transparent_tun"}
    except (TypeError, ValueError):
        return {"source": "macos_system_proxy", "state": "invalid",
                "proxy_client": "system_proxy", "proxy_url": ""}


def inspect_listener_owner(proxy_url: str) -> str:
    """Read-only localhost TCP listener process provenance, never port-based guessing.

    Returns 'shadowrocket' only if the actual listener executable belongs to the
    signed app's normal path; other/unreadable listeners receive no vendor claim.
    No raw process arguments, remote addresses or PIDs leave this function.
    """
    from urllib.parse import urlsplit
    try:
        address = urlsplit(proxy_url)
        if address.hostname not in ("127.0.0.1", "::1", "localhost"):
            return "unverified"
        port = address.port
        if not port or not 1 <= port <= 65535:
            return "unverified"
        listing = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-sTCP:LISTEN", "-iTCP:" + str(port), "-Fp"],
            capture_output=True, text=True, check=False, timeout=2)
        if listing.returncode != 0:
            return "unverified"
        pids = [line[1:] for line in listing.stdout.splitlines()
                if line.startswith("p") and line[1:].isdigit()][:10]
        found_other = False
        for pid in pids:
            item = subprocess.run(["/bin/ps", "-p", pid, "-o", "command="],
                                  capture_output=True, text=True, check=False, timeout=1)
            if item.returncode != 0:
                continue
            path = item.stdout.strip().split(" ", 1)[0]
            if "/Shadowrocket.app/Contents/" in path and (
                path.endswith("/Shadowrocket") or path.endswith("/MacPacketTunnel")
            ):
                return "shadowrocket"
            found_other = True
        return "other" if found_other else "unverified"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "unverified"


def inspect() -> dict:
    try:
        p = subprocess.run(["/usr/sbin/scutil", "--proxy"], text=True,
                           capture_output=True, check=False, timeout=3)
        if p.returncode != 0:
            raise OSError("scutil failed")
        observed = parse_scutil(p.stdout)
        if observed.get("state") == "explicit":
            observed["listener_owner"] = inspect_listener_owner(
                observed.get("proxy_url", ""))
            observed["listener_owner_source"] = "macos_tcp_listener_executable"
        return observed
    except (OSError, subprocess.TimeoutExpired):
        return {"source": "macos_system_proxy", "state": "unavailable",
                "proxy_client": "unknown", "proxy_url": ""}


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, separators=(",", ":")))
