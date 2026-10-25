#!/usr/bin/env python3
"""Fail-closed Codex stream circuit breaker for one Shadowrocket fallback group.

The only write target is a strict, known-nodes-only regex in the native
OpenAI-Resilience group editor, via an Accessibility-granted signed helper.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

HOME = Path.home() / "Library/Application Support/OpenAILinkGuardian"
STATE = HOME / "auto_route_state.json"
APP = Path.home() / "Applications/TunnelSentinelRouteController.app/Contents/MacOS/TunnelSentinelRouteController"
CANDIDATES = ("JAPAN 04", "JAPAN 14", "SEATTLE 05", "SAN JOSE 07")
ORIGINAL = "(?i)(" + "|".join(CANDIDATES) + ")"
COOLDOWN = 600
MAX_ACTIONS_PER_DAY = 3
MAX_ERROR_AGE = 210
MAX_EXCLUSIONS = 2
BACKEND_VERIFY_TIMEOUT = 180

def rule_for(excluded):
    remains=[node for node in CANDIDATES if node not in set(excluded)]
    if len(remains) < 2:
        raise ValueError("at least two candidates required")
    return "(?i)("+"|".join(remains)+")"

def default_state():
    return {
        "phase": 0, "excluded": [], "rule": ORIGINAL,
        "previous_rule": ORIGINAL, "last_trigger_at": 0,
        "last_attempt_at": 0, "last_transition_at": 0,
        "previous_node": "", "selected_node": "",
        "status": "armed", "actions_today": 0,
        "day": "", "last_backend_verified": False,
        "rollback_attempted_for": 0, "last_reason": "",
        "last_controller_probe_at": 0, "controller_readiness": "not_checked",
        "last_seen_node": "",
    }

def load_state(path=STATE):
    try:
        previous=json.loads(path.read_text())
        if not isinstance(previous,dict):
            return default_state()
        return dict(default_state(),**{
            k:v for k,v in previous.items() if k in default_state()
        })
    except (OSError,ValueError):
        return default_state()

def persist(state,path=STATE):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,"w") as fp:
        json.dump(state,fp,ensure_ascii=False,indent=2)
        fp.write("\n")
    os.replace(tmp,path)

def decision(stream,state,now):
    if not isinstance(stream,dict) or stream.get("state")!="ok":
        return None,"no_codex_evidence"
    try:
        last=int(stream.get("last_at",0))
        scan=int(stream.get("scan_at",0))
        latest=stream.get("recent_counts")
        if not isinstance(latest,dict):
            return None,"missing_short_window_evidence"
        count=sum(int(latest.get(k,0)) for k in
            ("broken_pipe","websocket_handshake","connection_reset"))
    except (TypeError,ValueError):
        return None,"invalid_evidence"
    if not 0<=now-scan<=90:
        return None,"stale_codex_scan"
    if last<=0 or last<=int(state["last_trigger_at"]):
        return None,"already_handled_or_no_recent"
    if not 0<=now-last<=MAX_ERROR_AGE:
        return None,"not_recent"
    if count<3:
        return None,"insufficient_errors"
    if now-int(state["last_attempt_at"])<COOLDOWN:
        return None,"cooldown"
    if state["actions_today"]>=MAX_ACTIONS_PER_DAY:
        return None,"daily_limit"
    if len(state.get("excluded",[]))>=MAX_EXCLUSIONS:
        return None,"candidate_safety_limit"
    return True,"qualified_stream_failure"

def parse_node(label):
    if not label.startswith("CURRENT_GROUP_NODE "):
        return None
    value=label.split("CURRENT_GROUP_NODE ",1)[1].strip().upper()
    found=[node for node in CANDIDATES if value.endswith(node)]
    return found[0] if len(found)==1 else None

def current_node(exe=APP):
    if not exe.exists():
        return None,"controller_not_installed"
    try:
        result=subprocess.run([str(exe),"--current"],capture_output=True,
                              text=True,check=False,timeout=6)
    except (OSError,subprocess.TimeoutExpired):
        return None,"controller_timeout"
    if result.returncode:
        return None,"group_not_visible_or_access_denied"
    node=next((parse_node(line) for line in result.stdout.splitlines()
               if parse_node(line)),None)
    return node,("ok" if node else "unexpected_node")

def run_editor(target,expected,exe=APP):
    try:
        result=subprocess.run(
            [str(exe),"--set",target,"--expect",expected],
            capture_output=True,text=True,check=False,timeout=12)
    except (OSError,subprocess.TimeoutExpired):
        return False,"controller_timeout"
    if result.returncode or "POLICY_PERSISTED group=OpenAI-Resilience" not in result.stdout:
        return False,"save_not_confirmed"
    return True,"saved_and_reopened"

def apply_transition(snapshot,state,exe=APP,now=None):
    now=int(time.time()) if now is None else int(now)
    day=time.strftime("%Y-%m-%d",time.localtime(now))
    if state["day"]!=day:
        state["day"]=day
        state["actions_today"]=0
    if snapshot.get("route_management")!="native_fallback" or snapshot.get("native_fallback_group")!="OpenAI-Resilience":
        return {"state":"disabled","reason":"not_native_group"}
    if state.get("status")=="policy_updated_awaiting_backend_evidence":
        if not snapshot.get("healthy",False):
            if (0<=now-int(state["last_transition_at"])<=300 and
                state["rollback_attempted_for"]!=state["last_transition_at"]):
                state["rollback_attempted_for"]=state["last_transition_at"]
                ok,reason=run_editor(state["previous_rule"],state["rule"],exe)
                if ok:
                    state["rule"]=state["previous_rule"]
                    state["excluded"]=state.get("excluded",[])[:-1]
                    state["phase"]=len(state["excluded"])
                    state["status"]="rolled_back_after_public_failure"
                    return {"state":state["status"],"reason":"public_edge_unhealthy",
                            "phase":state["phase"]}
                state["status"]="rollback_blocked"
                return {"state":state["status"],"reason":reason}
        node,reason=current_node(exe)
        if node and node in CANDIDATES and node not in state["excluded"] and node!=state["previous_node"]:
            state["selected_node"]=node
            state["last_backend_verified"]=True
            state["status"]="armed"
            return {"state":"armed","reason":"native_group_selected_new_node","node":node,
                    "phase":state["phase"]}
        if now-int(state["last_transition_at"])>BACKEND_VERIFY_TIMEOUT:
            state["status"]="backend_unverified"
        return {"state":state["status"],"reason":"waiting_for_native_group_selection",
                "phase":state["phase"]}
    if not snapshot.get("healthy",False):
        return {"state":"suppressed","reason":"public_edge_down"}
    if state["status"] not in ("armed","rolled_back_after_public_failure"):
        return {"state":state["status"],"reason":"manual_review_required"}
    qualified,reason=decision(snapshot.get("codex_stream_diagnostics",{}),state,now)
    if not qualified:
        return {"state":state["status"],"reason":reason,"phase":state["phase"]}
    node,proof=current_node(exe)
    if node is None:
        state["status"]="controller_unavailable"
        return {"state":state["status"],"reason":proof}
    if node in state.get("excluded",[]):
        state["status"]="policy_or_backend_mismatch"
        return {"state":state["status"],"reason":"selected_excluded_node"}
    excluded=list(state.get("excluded",[]))
    if len(excluded)>=MAX_EXCLUSIONS:
        return {"state":"candidate_safety_limit"}
    excluded.append(node)
    desired=rule_for(excluded)
    previous=state.get("rule",ORIGINAL)
    state["last_attempt_at"]=now
    state["last_trigger_at"]=int(snapshot["codex_stream_diagnostics"]["last_at"])
    ok,why=run_editor(desired,previous,exe)
    if not ok:
        state["status"]="controller_unavailable"
        return {"state":state["status"],"reason":why}
    state["excluded"]=excluded
    state["rule"]=desired
    state["previous_rule"]=previous
    state["previous_node"]=node
    state["phase"]=len(excluded)
    state["last_transition_at"]=now
    state["last_backend_verified"]=False
    state["status"]="policy_updated_awaiting_backend_evidence"
    state["actions_today"]+=1
    return {"state":state["status"],"reason":"native_fallback_rule_changed",
            "excluded_node":node,"phase":state["phase"],"backend_verified":False}

def enabled(path=HOME/"config.json"):
    try:
        config=json.loads(path.read_text())
        return (config.get("codex_auto_failover_enabled") is True
            and config.get("native_fallback_enabled") is True
            and config.get("native_fallback_group")=="OpenAI-Resilience"
            and config.get("codex_stream_sqlite_monitor_enabled") is True)
    except (ValueError,TypeError,OSError):
        return False

@contextlib.contextmanager
def single_writer(path):
    lock=path.with_name("auto_route.lock")
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle,fcntl.LOCK_UN)

def background_preflight(config_path=HOME/"config.json",
                         output=HOME/"auto_route_preflight.json",
                         exe=APP):
    """One bounded, no-write probe from actual LaunchAgent context."""
    try:
        cfg=json.loads(config_path.read_text())
    except (OSError,ValueError):
        return 0
    if cfg.get("codex_auto_preflight_enabled") is not True:
        return 0
    report={"source":"tunnelsentinel_signed_controller",
            "timestamp":int(time.time()),
            "controller_access":"unknown","native_group_ui":"not_checked"}
    try:
        perm=subprocess.run([str(exe),"--check-permissions"],capture_output=True,
                            text=True,timeout=5,check=False)
        report["controller_access"]="granted" if perm.returncode==0 else "required"
        if perm.returncode==0:
            current=subprocess.run([str(exe),"--current"],capture_output=True,
                                   text=True,timeout=7,check=False)
            node=next((parse_node(line) for line in current.stdout.splitlines()
                       if parse_node(line)),None)
            report["native_group_ui"]="readable" if current.returncode==0 and node else "not_available"
            report["node"]=node or ""
    except (OSError,subprocess.TimeoutExpired):
        report["controller_access"]="timeout_or_unavailable"
    # narrow, user-accessible diagnostic file; never raw logs, paths or stdout.
    persist(report,output)
    return 0

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-if-enabled",action="store_true")
    parser.add_argument("--observe-only",action="store_true")
    parser.add_argument("--state",type=Path,default=STATE)
    parser.add_argument("--snapshot",type=Path,default=HOME/"status.json")
    parser.add_argument("--config",type=Path,default=HOME/"config.json")
    args=parser.parse_args()
    if not args.run_if_enabled and not args.observe_only:
        return 2
    if args.run_if_enabled and not enabled(args.config):
        return background_preflight(args.config)
    with single_writer(args.state) as acquired:
        if not acquired:
            return 0
        try:
            snapshot=json.loads(args.snapshot.read_text())
        except (OSError,ValueError):
            return 2
        now=int(time.time())
        try:
            stamp=datetime.strptime(snapshot["updated_at"],"%Y-%m-%dT%H:%M:%S%z").timestamp()
            if not 0<=now-stamp<=100:
                return 0
        except (KeyError,ValueError,TypeError):
            if args.run_if_enabled:
                return 0
        state=load_state(args.state)
        if args.observe_only:
            qualified,reason=decision(snapshot.get("codex_stream_diagnostics",{}),state,now)
            print(json.dumps({"state":"observation_only","qualified":bool(qualified),"reason":reason}))
            return 0
        # Passive readiness evidence on every scheduled cycle, even without
        # recent errors. This does not open a sheet or alter any network route.
        observed,readiness=current_node()
        state["last_controller_probe_at"]=now
        state["controller_readiness"]=readiness
        if observed:
            state["last_seen_node"]=observed
        response=apply_transition(snapshot,state,now=now)
        state["last_reason"]=response.get("reason","")
        persist(state,args.state)
        print(json.dumps(response,ensure_ascii=False))
        return 0

if __name__=="__main__":
    raise SystemExit(main())
