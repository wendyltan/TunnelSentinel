#!/usr/bin/env python3
"""Codex-aware Shadowrocket group-level circuit breaker.

Only outputs permit-listed regex phases to the separately authorized native
GUI controller. Never changes global routing, node subscriptions or Tailscale.
No credential / prompt / application content is stored or emitted.
"""
from __future__ import annotations
import json
import fcntl
import contextlib
import os
from pathlib import Path
import subprocess
import time

HOME = Path.home() / "Library/Application Support/OpenAILinkGuardian"
STATE = HOME / "auto_route_state.json"
APP = Path.home() / "Applications/TunnelSentinelRouteController.app/Contents/MacOS/TunnelSentinelRouteController"
PHASES = [
    "(?i)(JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07)",
    "(?i)(JAPAN 04|JAPAN 14|SAN JOSE 07)",
    "(?i)(JAPAN 04|JAPAN 14)",
    "(?i)(JAPAN 14)",
]
COOLDOWN = 10 * 60
MAX_ACTIONS_PER_DAY = 3
MAX_ERROR_AGE = 210

def default_state():
    return {
        "phase": 0, "last_trigger_at": 0, "last_attempt_at": 0,
        "last_transition_at": 0, "status": "armed", "actions_today": 0,
        "day": "", "last_backend_verified": False,
    }

def load_state(path=STATE):
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            return default_state()
        return dict(default_state(), **{k:v for k,v in value.items() if k in default_state()})
    except (OSError,ValueError):
        return default_state()

def persist(state, path=STATE):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp,os.O_WRONLY | os.O_CREAT | os.O_TRUNC,0o600)
    with os.fdopen(fd,"w") as out:
        json.dump(state,out,ensure_ascii=False,indent=2)
        out.write("\n")
    os.replace(tmp,path)

def decision(stream, state, now):
    if not isinstance(stream,dict) or stream.get("state")!="ok":
        return None,"no_codex_evidence"
    latest = stream.get("last_at",0)
    try:
        latest = int(latest)
        counts = stream.get("recent_counts")
        if not isinstance(counts, dict):
            return None, "missing_short_window_evidence"
        critical = sum(int(counts.get(x,0)) for x in
                       ("broken_pipe","websocket_handshake","connection_reset"))
    except (ValueError,TypeError):
        return None,"invalid_evidence"
    if int(stream.get("scan_at",0)) <= 0 or not 0 <= now-int(stream["scan_at"]) <= 90:
        return None,"stale_codex_scan"
    if latest <= 0:
        return None,"no_recent_errors"
    if latest <= int(state["last_trigger_at"]):
        return None,"already_handled"
    if not 0 <= now-latest <= MAX_ERROR_AGE:
        return None,"not_recent"
    if critical < 3:
        return None,"insufficient_errors"
    if now-int(state["last_attempt_at"])<COOLDOWN:
        return None,"cooldown"
    if state["actions_today"]>=MAX_ACTIONS_PER_DAY:
        return None,"daily_limit"
    phase = int(state["phase"])
    if phase >= len(PHASES)-1:
        return None,"candidates_exhausted"
    return phase+1,"qualified_stream_failure"

def apply_transition(snapshot, state, exe=APP, now=None):
    now=int(time.time()) if now is None else int(now)
    today=time.strftime("%Y-%m-%d",time.localtime(now))
    if state["day"] != today:
        state["day"]=today
        state["actions_today"]=0
    if (snapshot.get("route_management")!="native_fallback" or
         snapshot.get("native_fallback_group")!="OpenAI-Resilience"):
        return {"state":"disabled","reason":"not_expected_native_policy"}
    if not snapshot.get("healthy",False):
        # Fail closed: a newly filtered group that loses basic public routing
        # is reverted ONCE, to avoid an unbounded loop on an already broken net.
        phase=int(state.get("phase",0))
        changed=int(state.get("last_transition_at",0))
        if (phase>0 and 0 <= now-changed < 300 and
                int(state.get("rollback_attempted_for",0)) != changed):
            state["rollback_attempted_for"]=changed
            if exe.exists():
                try:
                    result=subprocess.run(
                        [str(exe),"--set",PHASES[phase-1],"--expect",PHASES[phase]],
                        capture_output=True,text=True,check=False,timeout=13,
                    )
                    if result.returncode==0:
                        state["phase"]=phase-1
                        state["last_attempt_at"]=now
                        state["status"]="rolled_back_after_public_failure"
                        return {"state":state["status"],"phase":state["phase"],
                                "reason":"public_route_failed_after_group_change"}
                except (OSError,subprocess.TimeoutExpired):
                    pass
            state["status"]="rollback_blocked"
            return {"state":state["status"],"reason":"controller_unavailable_on_rollback",
                    "phase":phase}
        return {"state":"suppressed","reason":"public_edge_down","phase":phase}
    # An unverified or failed edit is a hard stop, not permission to
    # exclude more nodes. A separate native log observation must reconcile.
    if state.get("status") in (
        "policy_updated_awaiting_backend_evidence","rollback_blocked",
        "permission_or_ui_blocked","controller_unavailable","controller_error",
        "no_controller",
    ):
        return {"state":state["status"],
                "reason":"awaiting_verification_or_explicit_recovery",
                "phase":state["phase"]}
    phase, reason=decision(snapshot.get("codex_stream_diagnostics"),state,now)
    if phase is None:
        return {"state":state["status"],"reason":reason,"phase":state["phase"]}
    expected=PHASES[int(state["phase"])]
    target=PHASES[phase]
    state["last_attempt_at"]=now
    state["last_trigger_at"]=int(snapshot["codex_stream_diagnostics"]["last_at"])
    if not exe.exists():
        state["status"]="no_controller"
        return {"state":"no_controller","reason":"controller_not_installed","phase":state["phase"]}
    try:
        result=subprocess.run(
            [str(exe),"--set",target,"--expect",expected],
            capture_output=True,text=True,check=False,timeout=13,
        )
    except (OSError,subprocess.TimeoutExpired):
        state["status"]="controller_unavailable"
        return {"state":"controller_unavailable","reason":"timeout_or_unavailable","phase":state["phase"]}
    if result.returncode:
        state["status"]="permission_or_ui_blocked" if result.returncode==77 else "controller_error"
        return {"state":state["status"],"reason":"failed_closed_no_change","phase":state["phase"]}
    # Only the allowlist regex was saved. Actual backend selection requires
    # subsequent native fallback background check / per-request logs.
    state["phase"]=phase
    state["actions_today"]+=1
    state["last_transition_at"]=now
    state["last_backend_verified"]=False
    state["status"]="policy_updated_awaiting_backend_evidence"
    return {
        "state":state["status"],"reason":"native_group_candidate_filter_changed",
        "phase":phase,"previous":phase-1,
        "last_action_at":now,"backend_verified":False,
    }

def enabled(config_path=HOME / "config.json"):
    try:
        config=json.loads(config_path.read_text())
        return (config.get("codex_auto_failover_enabled") is True
                and config.get("native_fallback_enabled") is True
                and config.get("native_fallback_group") == "OpenAI-Resilience"
                and config.get("codex_stream_sqlite_monitor_enabled") is True)
    except (OSError,ValueError,TypeError):
        return False

@contextlib.contextmanager
def nonconcurrent(state_path):
    path=state_path.with_name("auto_route.lock")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a+") as file:
        try:
            fcntl.flock(file,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(file,fcntl.LOCK_UN)

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--state",type=Path,default=STATE)
    parser.add_argument("--snapshot",type=Path,default=HOME/"status.json")
    parser.add_argument("--observe-only",action="store_true")
    parser.add_argument("--run-if-enabled",action="store_true")
    parser.add_argument("--config",type=Path,default=HOME / "config.json")
    args=parser.parse_args()
    if args.run_if_enabled and not enabled(args.config):
        return 0
    # Applying a change is never the default behavior for ad-hoc invocation.
    if not args.observe_only and not args.run_if_enabled:
        return 2
    with nonconcurrent(args.state) as acquired:
        if not acquired:
            return 0
        return run_cycle(args)

def run_cycle(args):
    state=load_state(args.state)
    try:
        status=json.loads(args.snapshot.read_text())
    except (ValueError,OSError):
        print(json.dumps({"state":"no_status"}));return 2
    now=int(time.time())
    try:
        from datetime import datetime
        stamp=datetime.strptime(status["updated_at"],"%Y-%m-%dT%H:%M:%S%z").timestamp()
        if not (0 <= now-stamp <= 100):
            print(json.dumps({"state":"no_fresh_guardian_snapshot"}))
            return 0
    except (ValueError,KeyError,TypeError):
        # Test snapshots may not have updated_at; in any real run the field is mandatory.
        if args.run_if_enabled:
            return 0
    if args.observe_only:
        stage,reason=decision(status.get("codex_stream_diagnostics",{}),state,now)
        print(json.dumps({"state":"observation_only","qualified_phase":stage,"reason":reason},ensure_ascii=False))
        return 0
    report=apply_transition(status,state,now=now)
    persist(state,args.state)
    print(json.dumps(report,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
