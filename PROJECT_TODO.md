# TunnelSentinel — outstanding acceptance

## P0 · Proven autonomous recovery (OPEN)

- [x] Stop looping over stale subscription names; use recently successful verified candidates.
- [x] Shorten degraded detection checks without changing normal network checks.
- [x] Do not auto-rotate from mere 429/Cloudflare client diagnostics.
- [x] Verify selection and a fresh edge request before declaring recovery; classify selector failure and back off.
- [x] Menu displays recovery failure and offers open-Shadowrocket action.
- [x] 菜单栏实时文字与主面板右上角徽标使用同一状态来源（系统菜单栏实时可访问性确认成功；用户视觉验收仍待执行）。
- [x] Shadowrocket 原生 `fallback` 方案与独立示例片段完成，保留现有 Config 规则，未改动运行配置。
- [ ] 在 Shadowrocket **复制的测试配置** 中新建代理分组并明确将 OpenAI 规则指向该分组；核查真实命中（包括 ChatGPT/Codex WebSocket）并由用户验收后才激活。
- [ ] **Prove automatic node selection on this Mac.** Both background URL scheme and foreground activated URL scheme returned without changing the selected node. Do not claim failover succeeds. Investigate Shadowrocket native fallback/url-test groups or a verified, explicitly approved macOS control path. Do not edit subscription secrets or install competing proxy stacks.
- [ ] Prove full integration: selected node physically changes and ChatGPT public probe succeeds, then app diagnostics recover after fresh client events.
- [ ] Human visual acceptance of menu recovery state and action.

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
