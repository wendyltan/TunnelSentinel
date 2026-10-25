# TunnelSentinel — unattended GPT route recovery design (2026-10-25)

## Verified present state

- Mac Shadowrocket 2.2.92 currently drives system packet tunnel; `OpenAI-Resilience` is native `fallback` with one bound subscription and a four-name regex. It can perform its own transport availability fallback independent of our UI, but that does not guarantee authenticated Codex WebSocket stream longevity.
- Our in-process `IntegratedGroupController.currentNode()` reads a visible Shadowrocket AX row (`OpenAI-Resilience ... FALLBACK > ...`). Its availability changes when the user navigates away / locks the screen. It has no confirmed unattended group-selection API; there is no Shadowrocket AppleScript dictionary from `sdef`, and inspecting public `CFBundleURLTypes` finds registered URL schemes, not documented group-targeted control semantics.
- Guardian observes ChatGPT public edge separately from actual upstream node. `JP-NRT` is the sampled Cloudflare data center region, NOT provider server name. The optional native request logger remains disabled because background access to Shadowrocket protected data requires separate user authorization. No private data permissions should be bypassed.
- The controller is still hard-coded to 4 exact node names and a canonical regex, and has no safe subscription migration. Current native controller is usable opportunistically when its GUI prerequisites hold, not guaranteed 24/7.

## Two compatibility tracks

### Track A — Shadowrocket as exclusive tunnel (low disruption)

1. Keep its subscription-bound native fallback for ordinary node-unavailable failures. Make candidate eligibility flexible through the subscription's visible group rules, including configurable region/name matching and at least two candidates. **Do not auto-remove entire group filters or bind an arbitrary provider when subscription changes.**
2. Distinguish live control readiness from stream monitoring: `armed` only when the group is currently readable, `limited` when the app cannot confirm ability to change it. This is implemented now; no route changes.
3. Allow documented, explicitly authorized, minimal request-level route observation: exact allowlisted GPT hosts only, node/policy/timestamp only, no URL/query/headers. Prefer a user-picked scoped directory bookmark or supported diagnostics export if possible. On no auth or no recent requests, show unknown.
4. Use original native AX UI only as optional human-present control. Do NOT auto-focus or click through foreground windows at night/locked screen. Even with logs, there is no reliable group-level write API; *unattended business-triggered switching remains unguaranteed.*

### Track B — controllable GPT-specific routing engine (needs owner's architecture decision)

- Evaluate a headless, loopback-bound Mihomo core; TunnelSentinel stays the **single GUI App**. Official Mihomo docs describe `GET /proxies`, `PUT /proxies/{name}`, `GET /providers/proxies`, provider refresh and per-node health checks. These are testable, documented control surfaces independent of AppKit GUI state.
- Sources: https://wiki.metacubex.one/en/api/ and https://wiki.metacubex.one/en/config/proxy-providers/
- Build an isolated offline proof first (fake subscription names, no credentials, no system/VPN routing mutation) covering provider additions/removals, switch/read-back, parser compatibility, restart recovery, and app sleep/wake. No extra menu bar app is needed.
- To run for real, prove how *only the desired GPT/Codex traffic* reaches this engine without double-proxying/looping through Shadowrocket; document domain/TUN ownership and rollback. Never run two competing TUNs, change global system proxy, or start a second live VPN for experiments.
- Explicit approval needed before introducing a new active proxy core, importing subscriptions/credentials, or migrating an existing active policy. Protect API by loopback binding plus authentication and never log subscription URLs/tokens.

## Capability contract for any backend

- `discoverProviders`: list active provider source identity and subscription-derived candidates, with no secret URLs in logs; stable node identifiers use nonsecret provider ID + node handle, collision handling and rename detection.
- `observeActiveGroup`: return `observed_node`, data source, capture time, confidence (`public_egress`, `group_selection`, `native_request_route`, `stream_success` are DISTINCT).
- `readCandidates` and `readConfigRevision`: do not infer candidate membership from public IP.
- `switchGroup(to, expectRevision)`: atomic compare-and-swap control with confirm readback and explicit route owner.
- `rollback(snapshot)`: exact prior policy, with one-shot bounded retry.
- `health(node)`: public edge reachability, latency and *actual Codex stream errors* reported separately. No background paid/authenticated requests without user authorization.
- `capabilities`: `can_observe_public`, `can_read_group`, `can_change_group`, `can_import_provider`, `can_prove_stream_recovery` independently. UI must not collapse them into one green status.

## Recovery state machine

`healthy -> suspect -> eligible -> switching -> route_verified -> business_verified` with `limited` and `blocked` explicit. Trigger only after recent repeated *Codex-specific* connection errors, identify whether the issue affects just one node, and rank eligible other candidates using valid recent samples (never assume lowest TCP ping = authenticated success). After a switch, verify policy and observe the next real Codex stream; route verification alone is not business success. Quarantine the suspect candidate temporarily; use bounded probation/recovery to re-include it automatically after real favorable evidence. Preserve operator-selected node/route and prevent cross-provider surprise.

## Acceptance and rollback

1. No current profile/route/VPN mutation in research or dry-run.
2. Switch works when Shadowrocket app is not frontmost and screen is locked (backend track B only, after owner permits live architecture); if not, status must say limited.
3. Subscription renamed, removed, replaced or temporarily empty -> no wrong node, no leaked credentials, clear alert.
4. No switching for HTTP 429 / Cloudflare challenge alone; no switching on expired diagnostics, permission denied, or insufficient evidence.
5. Avoid flapping: bounded cooldown, single action owner, loop prevention, candidate quarantine and recovery; rollback on fresh public edge regression.
6. User-visible data separates current request node, group-selected node, sampled public egress, and stale observations.
7. Verify actual Codex successful stream, not only a green probe or rule Save action.

## Recommended next implementation order

P0a — accurate readiness + user-facing limited status (implemented, 2026-10-25). P0b — offline provider/candidate/control adapter and replayable fake events. P1 — live read-only diagnostics with user-granted scope, plus subscription change detection. P2 — owner-selected backend architecture and isolated proof. P3 — after approved deployment, real route switch verification, adaptive candidate recovery, lockscreen and sleep/wake tests. Do not enable live Track B implicitly.
