# TunnelSentinel — Handoff

## Latest verified update · 2026-10-23 14:54 CST

- User reports frequent failures loading conversations in the macOS ChatGPT desktop app. On Mac mini, runtime Guardian `v1.4.4` was healthy by public-edge probe, but short failures were logged near 14:34 and 14:39 (each followed by recovery). Actual desktop logs recorded `Thread catalog sync failed` with authenticated HTTP **403** at 14:43, followed by `cloudflare_challenge` events and recurrent PubSub close/open events. These events correlate with the symptom but do not uniquely prove one node or one domain is at fault.
- An anonymous curl via the existing local proxy returned HTTP 200 for public `chatgpt.com/cdn-cgi/trace`, HTTP 404 for `ws.chatgpt.com/`, and an SSL handshake failure for `desktop.chat.openai.com`. These differing anonymous responses are **diagnostic observations only**, not an authenticated desktop-app end-to-end verdict.
- Scoped fix: Guardian `v1.4.6` now separately classifies real `Thread catalog sync failed` events as `thread_sync` / `会话列表同步失败`, preserving 429 classification precedence. Event appears in the existing business issue list for three minutes; public-edge `healthy` stays independent, and business 403 never triggers node rotation. Python 41 tests + `py_compile` and `git diff --check` passed.
- **LIVE:** Source was copied atomically to existing `~/Library/Application Support/OpenAILinkGuardian/openai_link_guardian.py` after backup at `backups/thread-sync-before-v146-20261023/`; only Guardian LaunchAgent restarted. Live status 14:53:42 reports v1.4.6, healthy, native fallback `OpenAI-Resilience` enabled, public egress US-SEA; ChatGPT, Shadowrocket and menu bar PIDs unchanged. Live `config.json` SHA-256 unchanged. No forced node failure / WebSocket lifetime test was performed.
- **Next safe investigation:** Shadowrocket native **测试规则** against official desktop/auth/Cloudflare challenge/WebSocket domains. Compare routing and log times when the next session-list failure occurs. Do not treat an anonymous TLS/403 response or one public HTTP 200 as definitive. The real failover fault-injection gate remains open and needs separate user permission.

**Historical snapshot (below):** 2026-10-22 ~22:10 CST · Mac mini · `/Volumes/ExtSSD/tools/TunnelSentinel`.
Always re-check `git status -sb`, HEAD, status.json and running LaunchAgents before acting. Current branch: `feature/tunnelsentinel-health-dashboard-20261022`.

## Present capabilities and real acceptance

- Backend v1.4.0; menu app v1.4.1, with ~30s normal / ~10s degraded public OpenAI edge probes; 72h recently proven candidate names; unconfirmed Shadowrocket selection triggers a bounded 15-minute backoff. Cloudflare challenge/429 stay as business diagnostics, not direct node-rotation triggers.
- Native signed menu app at `~/Applications/TunnelSentinel.app`, active via `com.wuwendi.tunnelsentinel-menu`; backend via `com.wuwendi.openai-link-guardian`. App branding uses a template menu glyph and an app icon. This stage **made the badge text itself** the macOS status title (same `statusLabel` used by the panel's upper-right badge), with native contrast/accessibility.
- **LIVE UI VERIFIED:** macOS Accessibility returned menu bar title `! 需留意` on this Mac, while guardian's live status was `healthy=true, overall_status=attention, business_status=attention` and selected server `🇯🇵 Japan 04`. User's aesthetic acceptance is not yet complete.
- Source tests: 38 Python tests passing (34 guardian + 4 safe policy fragment). Swift compiled, new signed menu app installed and launched; guard's PID was preserved. Exact backup path reported by installer; the last installed menu backup used a `branding-20261022-220227` directory. Do not claim hypothetical offline/paused menu variants visually tested.

## Active P0 blocker: native self-healing

- Shadowrocket 2.2.92, Global Routing **Config**, current rule file `sr_cnip.db.rule` is compiled nontext. Prior `shadowrocket://select` and `open -a ... shadowrocket://select` returned 0 **without changing the selected node**; external selector is not a proven recovery channel.
- Shadowrocket has native `fallback` group and `url-test` group support, but policy group must be **referenced by real routing rules**. For network stability use a `fallback` with a small, tested candidate pool rather than latency chasing. Public research references linked in `research/shadowrocket-native-failover.md`.
- Created **non-destructive draft** `examples/shadowrocket-openai-fallback.fragment.conf` with placeholder nodes and dedicated OpenAI domain policy; tested syntax structure and absence of credentials. **Not deployed into Shadowrocket**. No subscription, rule file, global routing, proxy, ChatGPT/Codex service altered in this phase.
- To actually enable, backup/duplicate Shadowrocket's current profile inside the app, create group there, verify node membership and OpenAI rule priority, then get approval before switching the active profile; finally prove traffic took fallback route and fresh public edge succeeded, followed by authenticated client diagnostics. Do NOT overwrite `*.db.rule` or claim end-to-end failover PASS without evidence.

## Files and next safe action

- `README.md`: public-facing description, status semantics and staged native failover feature.
- `PROJECT_TODO.md`: acceptance ledger for incomplete P0.
- `AGENTS.md`: privacy, narrow changes, verification and rollback rules.
- `research/shadowrocket-native-failover.md`: exact staged setup and gating.
- `examples/shadowrocket-openai-fallback.fragment.conf`: illustrative snippet, **not a standalone importable full profile**.

**Next:** User review of the live text badge, then an in-app *copied* Shadowrocket policy profile (non-active), with manual verification of its routing matches and explicit permission to activate for controlled testing. Keep both menus and guardian in place throughout.


## Actual Shadowrocket in-app attempt — 2026-10-22 ~22:29 CST

- User explicitly requested implementing real failover now. Mac mini Shadowrocket 2.2.92 Config mode, original active profile `sr_cnip.conf` (`CurrentRuleFileName=sr_cnip.db`, 393 UI rule entries), node `🇯🇵 Japan 04`. Public edge health remained `healthy=true`; ChatGPT diagnostic was `attention`.
- Before any UI edits: created a consistent, PRIVATE read-only recovery backup of original prefs, `sr_cnip.db.rule`, `groups.archive`, and SQLite `rule.db` under `~/Library/Application Support/OpenAILinkGuardian/backups/shadowrocket-before-native-fallback-20261022/` (permissions restricted; do not commit or expose contents).
- Via Shadowrocket's native UI, successfully **copied** `sr_cnip.conf` into **inactive** `sr_cnip-copy.conf`. Navigated to the copy's `代理分组` editor; opened `添加`, typed name `OpenAI-Resilience`, selected native **fallback** type. These form edits are **UNSAVED**; no candidate nodes selected yet.
- At strategy picker click, macOS unexpectedly denied `osascript` System Events accessibility with `-25211` several times; a read-only frontmost query still worked, but UI click blocked. Do not bypass OS accessibility permission or edit encrypted/compiled Shadowrocket files.
- Rechecked active profile: `sr_cnip.db` unchanged; node Japan 04 unchanged; guardian healthy. The user must authorize the appropriate GUI automation accessibility permission in macOS settings (or manually perform the few remaining UI edits) before automated UI work can resume. No live failover is enabled.
- **One next safe action:** request Accessibility authorization for the app/process controlling Mac GUI in System Settings > Privacy & Security > Accessibility; then continue on the **inactive copy**, add actual known existing nodes, bind OpenAI + WebSocket domain rules above broad rules, save/validate, only activate with rollback and real smoke test.


## Accessibility permission recheck — 2026-10-22 22:41 CST

- User screenshot of macOS System Settings > Privacy & Security > Accessibility shows AEServer, Terminal, node and Codex Computer Use enabled. `osascript` is **not** expected to show as an individual app necessarily.
- A read-only Swift check on Remote Desktop Commander terminal returned `AXIsProcessTrusted=true`. AppleScript `System Events` can still read Shadowrocket window title/position; however `System Events click at` returns `osascript not allowed assistive access (-25211)`, even after re-activating Shadowrocket. Thus *read access and trust boolean are insufficient to prove GUI action permission*; do not mark UI automation functional or blame user for missing a toggle.
- Shadowrocket UI remains on unsaved `OpenAI-Resilience` fallback group editor in the **inactive** copied profile. The form is scrolled to strategy/interval/URL. **No policy has been saved or activated**, and original profile `sr_cnip.conf` and node Japan 04 remained active. Existing Shadowrocket backup remains.
- Next: inspect privacy > Automation for `System Events` permission attributed to the responsible app (if shown) / retry only after macOS grants actual UI action; otherwise use non-privilege-escalating GUI interaction with the user, not file/database or alternate injection to bypass TCC denial.


## Automation screenshots & intermittent UI action — 2026-10-22 ~22:48 CST

- User screenshot System Settings > Privacy & Security > Automation shows Terminal -> System Events enabled and **one** expanded `node` -> System Events enabled. There is a *second distinct* collapsed `node` entry below it, whose System Events permission is not visible. This may be a different executable identity (Remote Desktop Commander process) and needs checking by the user; do not claim certain.
- Retest with no setting changes: `osascript` read window success; first attempt `click at` returned 0 but screenshot showed unchanged group form; second click attempt returned `-25211` assistive access denied. No group candidate added/saved. Do not bypass TCC via alternative injection. Ask user to expand the second `node` and verify System Events is authorized.
- Existing unsaved `OpenAI-Resilience` fallback group form remains on strategy/interval/URL section. Current active profile and node must be revalidated before making further changes.


## Early-morning retry — 2026-10-23 04:58 CST

- User requested one more attempt while away from Mac. Mac mini remains online and daemon status `healthy=true`, `overall_status=reachable`, `business_status=no_recent_errors`, selected node `🇯🇵 Japan 04`.
- Shadowrocket process and PacketTunnel are running, but `activate` shows no AX windows (count 0). `screencapture` returned a fully black image.
- **Verified root blocker:** Swift `CGSessionCopyCurrentDictionary` returned `CGSSessionScreenIsLocked = 1`. Do not unlock the Mac, simulate password entry, alter sleep settings, or change proxy profile while owner sleeps. The unsaved `OpenAI-Resilience` form from previous night is not accessible.
- Original active config remains `sr_cnip.db`. No new native fallback policy activated or saved. Attempt safely when owner unlocks local desktop. Existing private backup retained.


## 2026-10-23 07:18 CST — unlocked GUI continuation

- User unlocked Mac mini. Device online, Shadowrocket foreground window reopened (AX window count 1), and screenshot shows the **unsaved** fallback group editor at strategy/interval/URL. Public edge `healthy=true`, `overall_status=reachable`, `business_status=no_recent_errors`; Japan 04 and original active config `sr_cnip.db` unchanged.
- Re-tested actual System Events GUI click for green `+` in fallback strategy row (`click at {998,722}`). Denied **-25211**, even though `System Events UI elements enabled=true` and read-only Shadowrocket window inspections work. This matches documented nested-command-agent macOS assistive-access failures: remote helper may need correct attributable Accessibility grant; an authorization list with Terminal and node checked is not proof of actionable GUI control.
- Do not bypass via alternate mouse injection, editing Shadowrocket internal SQLite/rules, or resetting all TCC permissions; do not claim native fallback setup complete. The form has **not** gained a node or been saved.
- Smallest user action if present: directly click the green `+` beside 策略 in the open Shadowrocket popup; verify node selection UI, choose valid candidates, return to group setup. Any broader GUI automation needs legitimately approved control-app access, not an unchecked CLI workaround.


## 2026-10-23 07:25 CST — user opened strategy picker, missing subscription nodes

- User screenshot shows Shadowrocket `策略` picker lists only built-in policies (`PROXY`, `DIRECT`, `TAILSCALE`, `REJECT` variants), not subscribed Japan/US nodes. This is expected for a group without a bound subscription, NOT evidence subscription is empty.
- Shadowrocket documentation indicates fallback group editor has separate `订阅` switch which reveals `服务器节点` selector; after choosing a real subscription, its nodes become eligible in the group's strategies. Source: LOWERTOP/Shadowrocket wiki and https://free-nodes.github.io/shadowrocket/shadowrocket_manual.html.
- Instructed user to return to `OpenAI-Resilience` editor (do not select built-in `PROXY` or save an empty group), scroll to subscription switch, turn it on, choose the relevant current subscription. Next: filter to a small set of existing different-egress JP/US nodes, verify actual entries before saving; then bind the OpenAI/WebSocket domain rules in **inactive** `sr_cnip-copy.conf`. Original active profile untouched.


## 2026-10-23 — user manually selected active subscription in inactive fallback editor

- User screenshots **confirm** `OpenAI-Resilience` editing form: `fallback`, 订阅 enabled and 服务器节点 pointing to user's existing subscription. The populated 策略 list shows actual many nodes (HK / Singapore etc.), proving the subscription is selected but also indicating all subscription nodes are included by default.
- Form exposes 正则 (optional), interval **600 seconds**, timeout **5 seconds**, URL `http://www.gstatic.com/generate_204`. The group is not yet confirmed saved, and its OpenAI routing rules are not yet configured.
- Current guidance: use optional policy name regex `(?i)(JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07)` to limit to four previously observed useful candidates, verify resulting filtered names exist. Try 60s interval, 5s timeout, URL `https://chatgpt.com/cdn-cgi/trace`. If regex filters to zero or one node, do NOT save: inspect actual subscription names and adapt. The filter narrows candidates but does not guarantee health.
- After user verifies filter, save **only in inactive copied** `sr_cnip-copy.conf`, then add actual domain-to-group routing rules; do not activate profile until rule ordering and rollback verified.


## 2026-10-23 07:41 CST — Native fallback enabled and routing smoke PASS

- User saved fallback `OpenAI-Resilience` in inactive copy `sr_cnip-copy.conf`. Read-only `rule.db` inspection confirmed one native `DLWPolicyGroup` of type `fallback`, subscription binding, regex `(?i)(JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07)`, interval `60`, timeout `5`, and `https://chatgpt.com/cdn-cgi/trace`. No subscription secrets stored in git.
- GUI successfully opened the copy's Rule list. The **first existing blackmatrix7 OpenAI.list rule-set** was changed from `PROXY` to `OpenAI-Resilience`; other rules unchanged. We did not add redundant domains. The rule set contains suffixes for `chatgpt.com` and `openai.com`, covering `ws.chatgpt.com` and `api.openai.com`.
- Private original backup made under `~/Library/Application Support/OpenAILinkGuardian/backups/native-fallback-before-cutover-20261023-0728/`, including preferences, active compiled rule and SQLite backup. A test copy was **activated with Shadowrocket's own GUI**; active pref = `sr_cnip-copy.conf-984549565.db`. Original `sr_cnip.conf` retained in Config list for one-click rollback.
- Official Shadowrocket **测试规则** validated all three: `chatgpt.com`, `ws.chatgpt.com`, `api.openai.com` -> `DOMAIN-SUFFIX`, `OpenAI-Resilience`, runtime `🇺🇸 USA Seattle 05`. Global selected server remains `🇯🇵 Japan 04` (different from OpenAI group egress; not an error). Public edge HTTP 200 twice after cutover (~0.54–0.61 s); public api.openai.com/v1/models responds unauthenticated 401 (expected). Guardian later `healthy=true, overall_status=reachable, business_status=no_recent_errors`.
- Guardian v1.4.2 deployed in **native_fallback_enabled=true** and `native_fallback_group=OpenAI-Resilience` in live config; suppresses broken legacy external node selection, keeps public checks, client alerts and tunnel recovery. Config/script backup at `~/Library/Application Support/OpenAILinkGuardian/backups/native-fallback-guardian-before-v142-20261023/`.
- Native-aware menu app (v1.4.3) distinguishes global selected node from OpenAI group egress; fixes misleading `node_unverified` badge when macOS blocks reading global node (not a link fault).
- Regression suite: 39 Python tests pass, native menu Swift builds, full signed app deploy; real forced node-failure switching and logged-in long-term WebSocket stability **still untested**.
- **Rollback**: In Shadowrocket Config, choose original `sr_cnip.conf` and `使用配置`; revert live Guardian `native_fallback_enabled=false` if abandoning native group (preserved pre-v142 config backup), or keep native mode if the user plans to re-enable the group soon. Never perform destructive database changes.


## 2026-10-23 11:40 CST — Requested two-node visibility

- User wanted actual OpenAI node AND global selected Shadowrocket node shown concurrently in the menu bar and main popup. Existing code only used `group.com.liguangming.SelectedServerName`, which is global selection. A live direct proxy public edge request showed observed `ip=38.175.103.97`, `colo=SEA`, `loc=US` while global selection was `🇯🇵 Japan 04`. This confirms routing differs.
- Read-only inspection of Shadowrocket accessible preference state, compiled policy group metadata and group-archive object keys did **not** reveal a stable, read-only current-group-backend NAME API. Official Shadowrocket docs caution policy tests and instantaneous connection choice can differ, thus a previous `USA Seattle 05` label is **not** safe to cache as eternally live.
- Backend v1.4.4 reuses the existing `https://chatgpt.com/cdn-cgi/trace` probe body (no extra polling) to parse IP/colo/country with strict validation. Only successful fresh probe results set `openai_egress_*;` failed/unavailable probes clear those fields. `openai_group_backend_verified=false`, backend name deliberately empty until independently verified; never label egress IP as exact provider node.
- Signed menu app v1.4.4 shows two distinct fields: `OpenAI 实际出口 · 最近一次探测（非节点名）` with geo/IP, and `SHADOWROCKET · 全局手选节点` with exact global selected name. The compact status bar includes `出 US-SEA · 全 Japan 04` alongside the health label. When stale or unreadable, displays unknown instead of stale cached data; no ChatGPT/Shadowrocket/tunnel restart or proxy-rule modification.
- Need post-install runtime status check and user visual acceptance, plus eventual reliable Shadowrocket-native backend-name API if available. Do not claim this IP/colo is the exact subscription **server name**, nor that full failover is fault-injection-verified.


## Runtime note: macOS preference access 2026-10-23 11:47

- Backend dual-egress v1.4.4 deployed, recorded fresh `openai_egress_observed=true`, `openai_egress_ip=38.175.103.97`, `openai_egress_colo=SEA`, `openai_egress_country=US`; original global node value `🇯🇵 Japan 04` remains. Health `healthy=true`, client `business_status=attention`.
- First signed menu deployment displayed `! 需留意 · 出 US-SEA · 全 未核实` because macOS intermittently denied fresh node preference read; backend's stored node was known but not verified for *this cycle*. The v1.4.5 menu therefore labels fallback global node `上次记录 · 🇯🇵 Japan 04` (status bar `全 上次 Japan 04`), never implying a stale name is current.
- Current actual provider **node name** remains unverified; SEA/IP is a recent routed egress observation and is not equivalent to that name. A future read-only supported source from Shadowrocket is needed to make that label exact.
