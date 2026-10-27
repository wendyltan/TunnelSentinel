#!/usr/bin/env python3
"""Evidence-gated GPT node ranking, independent of proxy vendors.

NO traffic generation or proxy mutations. Inputs must come from separately
audited, per-node probing adapters. Unknown is never converted to healthy.
"""

from __future__ import annotations
import time

MAX_AGE = 600
ALLOWED_PER_NODE_SOURCES = frozenset({
    "mihomo_per_proxy_api",
    "surge_per_policy_api",
    "shadowrocket_verified_independent_per_node",
})


def _fresh(at, now, *, age=MAX_AGE):
    return isinstance(at, (int, float)) and at > 0 and 0 <= now - at <= age


def assess(candidate, *, now, policy, profile_id):
    """Assess one node; per-node attribution cannot come from group/root probes."""
    base = {
        "name": candidate.get("name", ""),
        "verdict": "unverified",
        "confidence": "none",
        "reason": "缺少当前策略的逐节点业务可用性证据",
        "evidence_at": 0,
        "eligible_for_recommendation": False,
    }
    name = candidate.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 128:
        return base
    if candidate.get("policy") != policy or candidate.get("profile_id") != profile_id:
        base["reason"] = "节点不属于当前配置或当前策略组"
        return base

    probe = candidate.get("independent_probe") or {}
    if not isinstance(probe, dict):
        return base
    if probe.get("source") not in ALLOWED_PER_NODE_SOURCES or not probe.get("route_confirmed"):
        base["reason"] = "测试没有证明请求实际走了该候选节点"
        return base
    if not _fresh(probe.get("checked_at"), now):
        base["reason"] = "该候选的业务探测已过期"
        return base
    base["evidence_at"] = int(probe["checked_at"])

    if probe.get("tls_certificate_valid") is False or probe.get("chatgpt_edge_http_code") in (403, 429, 451, 502, 503, 504):
        base["verdict"] = "not_recommended"
        base["reason"] = "OpenAI 入口握手或响应异常"
        return base
    if not (probe.get("tls_certificate_valid") is True and
            probe.get("chatgpt_edge_http_code") == 200 and
            probe.get("codex_websocket_host_tls") is True):
        base["reason"] = "缺少 ChatGPT HTTPS 与 Codex WebSocket 主机的完整连通性证据"
        return base

    # These merely show feasibility to TRY the route; not successful GPT tasks.
    base.update({
        "verdict": "trial_candidate",
        "confidence": "openai_transport_only",
        "reason": "OpenAI HTTPS 与 Codex WebSocket 主机传输验证通过；仍未确认实际任务成功",
        "eligible_for_recommendation": True,
    })
    app = candidate.get("real_client_observation") or {}
    if not isinstance(app, dict):
        return base
    # A successful model-catalog GET or public WS handshake is insufficient.
    if (app.get("per_connection_route_proven") is not True or
        app.get("node") != name or app.get("profile_id") != profile_id or
        not _fresh(app.get("observed_at"), now, age=1800)):
        return base
    if app.get("client_error_count", 0) > 0:
        base.update(verdict="not_recommended", confidence="client_errors",
                    reason="近期真实 Codex 连接记录出现错误", eligible_for_recommendation=False)
        return base
    if (app.get("completed_codex_turns", 0) >= 2 and
        app.get("stable_stream_seconds", 0) >= 90):
        base.update(verdict="business_observed", confidence="real_codex_task_observation",
                    reason="曾经观察到该节点完成实际 Codex 回合且连接保持稳定；并不保证后续永不掉线")
    return base


def recommend(candidates, *, now=None, policy, profile_id):
    now = int(time.time() if now is None else now)
    result = {
        "source": "gpt_business_candidate_evaluator_v1",
        "checked_at": now,
        "state": "no_proven_candidate",
        "recommendation": None,
        "candidates": [],
        "limitations": (
            "Transport probes do not prove authenticated GPT success.",
            "Attribution to each real node is mandatory.",
            "No proxy changes or credential replay performed.",
        ),
    }
    if not policy or not profile_id:
        result["state"] = "profile_or_policy_unknown"
        return result
    if not isinstance(candidates, list) or len(candidates) > 128:
        result["state"] = "invalid_candidates"
        return result
    rows = [assess(x, now=now, policy=policy, profile_id=profile_id)
            for x in candidates if isinstance(x, dict)]
    result["candidates"] = rows
    eligible = [x for x in rows if x["eligible_for_recommendation"]]
    if not eligible:
        return result
    eligible.sort(key=lambda x: (
        x["verdict"] != "business_observed", -x["evidence_at"], x["name"].casefold()))
    winner = eligible[0]
    result["state"] = "business_evidence_available" if winner["verdict"] == "business_observed" else "transport_trial_only"
    result["recommendation"] = {
        "name": winner["name"],
        "confidence": winner["confidence"],
        "reason": winner["reason"],
    }
    return result
