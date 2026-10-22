# TunnelSentinel — Handoff

**Snapshot:** 2026-10-22 ~22:10 CST · Mac mini · `/Volumes/ExtSSD/tools/TunnelSentinel`.
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
