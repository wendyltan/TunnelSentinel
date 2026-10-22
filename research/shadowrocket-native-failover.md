# Shadowrocket native failover — non-destructive implementation note

**Status: controlled integration enabled and routing verified 2026-10-23; failure-triggered switching is NOT YET VERIFIED.** The template remains illustrative and is not a complete importable profile. The original `sr_cnip.conf` remains available for rollback.

## Confirmed live constraints

- Shadowrocket 2.2.92 is running in `Config` global routing mode. Its current rule file is a compiled binary `sr_cnip.db.rule`, which must not be edited or replaced by the monitoring tool. The live subscription and node secrets must remain untouched.
- `shadowrocket://select?s=...` and `open -a Shadowrocket` returned success but did **not** change the selection on this Mac, even with the app in foreground. So TunnelSentinel's external selection command cannot be treated as reliable failover.
- Public edge health can recover by an external/manual node switch, but does not prove ChatGPT client calls/streaming are fully healthy. A Cloudflare challenge from anonymous curl or server-side HTTP 429 cannot be fixed reliably by blind rotation.
- The internal manager's policy is not exposed via the normal CFPreferences keys we currently read. Never infer an activated fallback group merely from a healthy edge probe.

## Target architecture (avoid dual controllers)

Shadowrocket native `fallback` group should own per-request node failover. TunnelSentinel should observe:
1. Proxy listener / public OpenAI edge status;
2. recent authenticated desktop app failures;
3. actual route recovery and cooldown/alert, without simultaneously forcing selected-server URL schemes when a native group is managing the same traffic.

A `fallback` group is preferred over `url-test` for a stability goal: prioritize staying on a working route rather than chasing the lowest latency. Its testing interval is bounded, so an outage can still last until the next check; no zero-downtime guarantee.

## Proposed configuration (safe to review, not to import directly)

See `examples/shadowrocket-openai-fallback.fragment.conf`: it defines `OpenAI-Resilience` with three **placeholder** node names, `fallback`, URL `https://chatgpt.com/cdn-cgi/trace`, interval 120 s and timeout 5 s. It also supplies narrow OpenAI domain rules, including `*.chatgpt.com` (therefore `ws.chatgpt.com`), `*.openai.com`, `*.oaistatic.com`, `*.oaiusercontent.com`, `*.oaistatsig.com` and `*.openaimerge.com`. This is a starting set, **not** a full replacement for the [OpenAI networking allowlist](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps). Verify actual OpenAI and Codex HTTPS + WebSocket behavior. Third-party authentication/CDN domains may require additional routing for the user's specific case; do not blindly proxy globally shared Cloudflare and Apple domains.

**Real setup and acceptance sequence**:
1. In Shadowrocket, duplicate/export a safe backup of the *full currently used profile* inside the app. Do not edit `*.db.rule` directly, copy encrypted profile data into Git, or replace the full file with this fragment.
2. Verify candidate nodes actually exist in the subscription and are individually usable, with different egresses if possible. Select exact names from the app; avoid hardcoded past names.
3. In the copied profile, create a named `fallback` group and assign candidates. The official menu path is usually Profile ⓘ → Proxy Group → Add; macOS 2.2.92 UI positioning may differ.
4. Add the group to the **routing rules actually matching** OpenAI domains, before broader keyword and FINAL rules. Merely creating a group does not activate it.
5. Do a read-only check that routing will hit `OpenAI-Resilience`; only then perform a *user-authorized, reversible profile switch*. Keep the previous profile available for immediate rollback.
6. On approved integration smoke, prove traffic uses group policy, selected backend/egress changes when a target route really fails, public edge returns a fresh 200, and authenticated ChatGPT/Codex WebSockets (including `ws.chatgpt.com`) can connect and stay stable. Then look for actual authenticated desktop client error reduction. Passing only a public health check is not equivalent to complete recovery.

Avoid indiscriminate `启用回退` on the global `proxy` policy before understanding the candidate scope: the app may choose any node in the homepage list, including unsuitable ones.

## Public references

- [LOWERTOP / Shadowrocket Wiki](https://github.com/LOWERTOP/Shadowrocket/wiki): policy groups `fallback`, `url-test`, selection and fallback semantics.
- [LOWERTOP lazy.conf](https://github.com/LOWERTOP/Shadowrocket/blob/main/lazy.conf): `[Proxy Group]` syntax and rule parameters.
- [Shadowrocket advanced-group guide](https://doc.repcz.link/shadowrocket/advance/): configuration and matching hints.

## Acceptance gate

**OPEN**: No live fallback group or OpenAI-specific policy has been installed by this stage. The one required high-impact action is selecting a test copy of the Shadowrocket profile after its rules/candidates have been reviewed. Do not silently alter current traffic routing merely to close a task.


## Local live validation — 2026-10-23

- Created `OpenAI-Resilience` inside the inactive `sr_cnip-copy.conf` using Shadowrocket's own editor, with subscription selector, exact regex filter, 60-second interval, 5-second timeout and public OpenAI edge URL.
- Remapped the **existing first** OpenAI rule-set (blackmatrix7 `OpenAI.list`) from `PROXY` to `OpenAI-Resilience`, preserving the remaining 392 rules.
- Activated the copied profile through Shadowrocket GUI. New prefs show `sr_cnip-copy.conf-984549565.db`; global selected server remains `🇯🇵 Japan 04`.
- Shadowrocket Test Rules shows `chatgpt.com`, `ws.chatgpt.com`, `api.openai.com` matching group `OpenAI-Resilience` with chosen group backend `🇺🇸 USA Seattle 05`. This proves route selection even though global node still shows Japan 04.
- Two edge probes via the local HTTP proxy returned HTTP 200 after the profile switch. This does not prove logged-in WebSocket stability or node-failure recovery timing.
- Guardian switched to native-owner mode to suppress broken `shadowrocket://select` calls, while retaining tunnel reconnect and diagnostics. **Do not** revert to externally driven rotation while the copy is active.
- Rollback: within Shadowrocket Config list, select the preserved `sr_cnip.conf` and choose **使用配置**. The private backup made before cutover is under `~/Library/Application Support/OpenAILinkGuardian/backups/native-fallback-before-cutover-20261023-0728/`.
