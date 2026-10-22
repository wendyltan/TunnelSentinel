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
