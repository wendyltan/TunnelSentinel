#!/usr/bin/env python3
"""On-demand Codex/ChatGPT Work proxy environment manager.

Shares the existing Desktop .command managed markers. No daemon, no silent
port switching, no system proxy writes, no app restarts, no credentials.
Only a checked current macOS HTTP/HTTPS localhost proxy is eligible.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

BEGIN = "# >>> CHATGPT_PROXY_MANAGED_BEGIN >>>"
END = "# <<< CHATGPT_PROXY_MANAGED_END <<<"
NO_PROXY = "localhost,127.0.0.1,::1,*.local,*.lan,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,100.64.0.0/10"
MANAGED = re.compile(r"(?m)^" + re.escape(BEGIN) + r"\n.*?^" + re.escape(END) + r"[ \t]*\n?", re.S | re.M)
CONFLICT = re.compile(r"(?m)^\s*(?:export\s+)?(?:HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy)\s*=")
URL = re.compile(r'^http://127\.0\.0\.1:([1-9][0-9]{0,4})$')


class UnsafeEnv(ValueError):
    pass


def env_path() -> Path:
    return Path.home() / ".codex" / ".env"


def strip_managed(old: str) -> tuple[str, bool]:
    if old.count(BEGIN) != old.count(END) or old.count(BEGIN) > 1:
        raise UnsafeEnv("托管配置标记不完整或重复；未修改")
    if old.count(BEGIN) == 0:
        return old, False
    unmanaged, count = MANAGED.subn("", old, count=1)
    if count != 1:
        raise UnsafeEnv("未找到唯一的托管块；未修改")
    return unmanaged, True


def old_file(path: Path) -> tuple[str, bool]:
    if path.is_symlink():
        raise UnsafeEnv(".env 是符号链接；拒绝修改")
    if not path.exists():
        return "", False
    if not path.is_file():
        raise UnsafeEnv(".env 不是普通文件；拒绝修改")
    return path.read_text(encoding="utf-8"), True


def managed_url(old: str) -> str:
    _, exists = strip_managed(old)
    if not exists:
        return ""
    part = old.split(BEGIN, 1)[1].split(END, 1)[0]
    m = re.search(r'(?m)^HTTP_PROXY=["\']?(http://127\.0\.0\.1:[0-9]+)["\']?\s*$', part)
    return m.group(1) if m and URL.fullmatch(m.group(1)) else ""


def state(path: Path, current: str = "") -> dict:
    try:
        old, _ = old_file(path)
        unmanaged, has_managed = strip_managed(old)
        configured = managed_url(old)
        conflict = bool(CONFLICT.search(unmanaged))
        status = ("conflicting_unmanaged_keys" if conflict else
                  "unrecognized_managed_block" if has_managed and not configured else
                  "synced" if configured and current == configured else
                  "different_route" if configured and current else
                  "configured_route_unknown" if configured else "not_configured")
        return {"state": status, "managed_url": configured, "system_proxy_url": current,
                "has_managed_block": has_managed, "has_unmanaged_proxy_conflict": conflict}
    except (UnsafeEnv, UnicodeError, OSError) as e:
        return {"state":"unreadable_or_unsafe", "reason":str(e),
                "managed_url":"", "system_proxy_url":current}


def current_http_proxy() -> str:
    from system_proxy_observer import inspect
    observed = inspect()
    url = observed.get("proxy_url", "")
    # For Codex' HTTP_PROXY/HTTPS_PROXY only accept local HTTP proxies.
    if observed.get("state") != "explicit" or not URL.fullmatch(url):
        raise UnsafeEnv("当前系统路由不是明确的 127.0.0.1 HTTP/Mixed 代理，拒绝猜测备用端口")
    return url


def probe(url: str) -> None:
    if not URL.fullmatch(url) or not 1 <= int(URL.fullmatch(url).group(1)) <= 65535:
        raise UnsafeEnv("代理地址不符合允许的本机 HTTP 格式")
    try:
        p = subprocess.run(
            ["/usr/bin/curl", "--silent", "--show-error", "--noproxy", "",
             "--connect-timeout", "2", "--max-time", "7", "--proxy", url,
             "--output", "/dev/null", "--write-out", "%{http_code}",
             "https://chatgpt.com/robots.txt"],
            capture_output=True, text=True, timeout=9)
        if p.returncode != 0 or p.stdout.strip() != "200":
            raise UnsafeEnv("当前本地代理未通过 ChatGPT 公开 HTTPS 200 探测；未写入")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise UnsafeEnv("本地代理探测无法完成；未写入") from e


def make_block(url: str) -> str:
    return (BEGIN + "\n"
            "# TunnelSentinel 与桌面 ChatGPT 代理脚本共同管理；仅这段可撤销。\n"
            + f'HTTP_PROXY="{url}"\nHTTPS_PROXY="{url}"\n'
            + f'http_proxy="{url}"\nhttps_proxy="{url}"\n'
            + f'NO_PROXY="{NO_PROXY}"\nno_proxy="{NO_PROXY}"\n'
            + END + "\n")


def atomically_write(path: Path, data: str, exists: bool, previous: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        bdir = path.parent / "proxy-env-backups"
        bdir.mkdir(mode=0o700, exist_ok=True)
        backup = bdir / (".env.before-tunnelsentinel-" +
                         datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        backup.chmod(0o600)
    fd, tmp = tempfile.mkstemp(prefix=".env.tunnelsentinel.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.chmod(tmp, (path.stat().st_mode & 0o777) if exists else 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sync(path: Path, url: str, *, dry_run: bool = False, test_proxy: bool = True) -> dict:
    match = URL.fullmatch(url)
    if match is None or not 1 <= int(match.group(1)) <= 65535:
        raise UnsafeEnv("只支持当前系统明确的本机 HTTP 代理，不推测节点")
    old, existed = old_file(path)
    unmanaged, _ = strip_managed(old)
    if CONFLICT.search(unmanaged):
        raise UnsafeEnv(".env 还有其他程序管理的代理键，拒绝覆盖")
    # Current already-working desktop setup must never be rewritten or
    # invalidated by a transient HTTP probe. 'unchanged' is NOT a health proof.
    if managed_url(old) == url:
        return {"state":"unchanged", "proxy_url":url}
    if test_proxy:
        probe(url)
    new = unmanaged.rstrip("\n") + ("\n\n" if unmanaged.strip() else "") + make_block(url)
    if new == old:
        return {"state":"unchanged", "proxy_url":url}
    if not dry_run:
        atomically_write(path, new, existed, old)
    return {"state":"would_sync" if dry_run else "synced", "proxy_url":url}


def rollback(path: Path, *, dry_run: bool = False) -> dict:
    old, existed = old_file(path)
    unmanaged, managed = strip_managed(old)
    if not managed:
        return {"state":"not_managed"}
    if dry_run:
        return {"state":"would_rollback"}
    if unmanaged.strip():
        atomically_write(path, unmanaged, existed, old)
    else:
        # Keep a copy of the old managed .env before deleting it.
        bdir = path.parent / "proxy-env-backups"
        bdir.mkdir(mode=0o700, exist_ok=True)
        backup = bdir / (".env.before-tunnelsentinel-rollback-" +
                         datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        backup.chmod(0o600)
        path.unlink()
    return {"state":"rolled_back"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "sync", "rollback"])
    parser.add_argument("--env-path", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    path = args.env_path or env_path()
    try:
        if args.action == "status":
            try:
                url = current_http_proxy()
            except UnsafeEnv:
                url = ""
            result = state(path, url)
        elif args.action == "rollback":
            result = rollback(path, dry_run=args.dry_run)
        else:
            result = sync(path, current_http_proxy(), dry_run=args.dry_run)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (UnsafeEnv, UnicodeError, OSError) as exc:
        print(json.dumps({"state":"refused","reason":str(exc)},ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
