#!/usr/bin/env python3
"""Read-only Shadowrocket native failover preflight from existing monitor evidence.

This does not inspect protected Shadowrocket databases, probe candidate nodes,
write proxy settings, or assert business task success from a public HTTP 200.
"""
from __future__ import annotations
from datetime import date, datetime
import json
from pathlib import Path
import re
import time

HOME = Path.home() / "Library/Application Support/OpenAILinkGuardian"
LOG = Path.home() / "Library/Logs/OpenAILinkGuardian/guardian.log"
NEEDED_HOSTS = frozenset({"chatgpt.com", "ws.chatgpt.com", "api.openai.com"})
SOURCE = "shadowrocket_failover_preflight_v1"
AUDIT_TTL = 600


def assess(config, status, audit, *, now=None):
    now = int(time.time() if now is None else now)
    group = str(config.get("native_fallback_group") or "")
    owner = status.get("proxy_client") == "shadowrocket"
    configured = bool(config.get("native_fallback_enabled")) and bool(group)
    check_time = int(audit.get("checked_at") or 0)
    audit_fresh = bool(0 <= now-check_time <= AUDIT_TTL and check_time)
    rows = {x.get("host"): x for x in audit.get("rules", [])
            if isinstance(x, dict) and x.get("host") in NEEDED_HOSTS}
    values = [str(rows.get(h, {}).get("policy") or "") for h in NEEDED_HOSTS]
    audit_complete = (audit_fresh and audit.get("state") == "verified_rule_matches"
                      and len(rows) == len(NEEDED_HOSTS)
                      and all(values))
    exact_group_match = bool(audit_complete and all(v == group for v in values))
    if not owner:
        routing = "current_system_proxy_is_not_shadowrocket"
    elif not configured:
        routing = "native_group_not_configured"
    elif not audit_fresh:
        routing = "rule_audit_missing_or_stale"
    elif not audit_complete:
        routing = "rule_audit_incomplete_or_unavailable"
    elif not exact_group_match:
        routing = "required_openai_rules_do_not_match_fallback_group"
    else:
        routing = "group_rule_matched_but_runtime_selection_unproven"

    # Runtime request-to-node attribution must be independently demonstrated.
    runtime_confirmed = bool(status.get("native_group_route_verified") is True
                             and status.get("native_proxy_log_recent") is True)
    # Existing native_group_route_verified is intentionally fail-closed.
    manual_candidate = None
    return {
        "source": SOURCE, "checked_at": now,
        "current_proxy": "shadowrocket" if owner else "other_or_unknown",
        "configured_fallback_group": bool(configured),
        "audited_rule_age_seconds": max(0,now-check_time) if check_time else None,
        "audited_rule_match": bool(exact_group_match),
        "routing_gate": routing,
        "runtime_per_request_node_verified": runtime_confirmed,
        "native_failover_confirmed": False,  # no native choice/failover journal available
        "autonomous_route_write_safe": False,
        "manual_node_recommendation": manual_candidate,
        "recommendation_gate": "no_fresh_per_candidate_real_route_and_business_evidence",
        "next_verification": [
            "Repeat native Shadowrocket rule tester for chatgpt.com/ws.chatgpt.com/api.openai.com",
            "Verify that the live selected policy is the intended fallback group",
            "Verify native group type, test method/URL, interval, members and failure behavior",
            "Confirm actual request-to-node attribution before evaluating manual candidates"
        ],
        "note": "Proxy egress region, global selected node and public GET do not prove native failover or per-node task success"
    }


def _load(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def daily_log_summary(path=LOG, *, day=None):
    day = date.today() if day is None else day
    dayprefix = day.isoformat()+" "
    results = {"public_probe_samples":0,"public_probe_bad":0,
               "recovered_public_probe_events":0,"confirmed_egress_region_changes":0,
               "global_node_label_transitions":0}
    previous = None
    try:
        with Path(path).open(encoding="utf-8",errors="replace") as f:
            for line in f:
                if not line.startswith(dayprefix):
                    continue
                m = re.search(r"health=(ok|bad) node=(.*?) score=",line)
                if m:
                    results["public_probe_samples"] += 1
                    results["public_probe_bad"] += m.group(1)=="bad"
                    name = m.group(2)
                    if previous is not None and previous!=name:
                        results["global_node_label_transitions"] += 1
                    previous = name
                if "public edge reachable again sampled_outage_s=" in line:
                    results["recovered_public_probe_events"] += 1
                if "public edge egress changed; 2 healthy probes confirmed" in line:
                    results["confirmed_egress_region_changes"] += 1
    except OSError:
        pass
    return results


if __name__=="__main__":
    current = assess(_load(HOME/"config.json"),
                     _load(HOME/"status.json"),
                     _load(HOME/"shadowrocket_rule_audit.json"))
    current["daily_log"] = daily_log_summary()
    print(json.dumps(current,ensure_ascii=False,separators=(",",":")))
