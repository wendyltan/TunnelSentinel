# TunnelSentinel — outstanding acceptance

## P0 · Proven autonomous recovery (OPEN)

- [x] Stop looping over stale subscription names; use recently successful verified candidates.
- [x] Shorten degraded detection checks without changing normal network checks.
- [x] Do not auto-rotate from mere 429/Cloudflare client diagnostics.
- [x] Verify selection and a fresh edge request before declaring recovery; classify selector failure and back off.
- [x] Menu displays recovery failure and offers open-Shadowrocket action.
- [x] 菜单栏实时文字与主面板右上角徽标使用同一状态来源（系统菜单栏实时可访问性确认成功；用户视觉验收仍待执行）。
- [x] Shadowrocket 原生 `fallback` 方案与独立示例片段完成，保留现有 Config 规则，未改动运行配置。
- [ ] **真实 Shadowrocket fallback 部署受 macOS 权限阻塞**：已通过 Shadowrocket 自己的“复制”功能创建未启用的 `sr_cnip-copy.conf`；已在副本打开 `fallback` 分组编辑器并填写名称 `OpenAI-Resilience`，但尚未添加节点、保存分组或配置匹配规则。22:26 起 System Events 的 `osascript` 连续返回辅助访问拒绝 `-25211`，不要通过替代 API 绕过 macOS 访问控制。恢复所需权限后继续执行、对照原配置检查并在真实业务链路验证后再启用副本。
- [ ] **Prove automatic node selection on this Mac.** Both background URL scheme and foreground activated URL scheme returned without changing the selected node. Do not claim failover succeeds. Investigate Shadowrocket native fallback/url-test groups or a verified, explicitly approved macOS control path. Do not edit subscription secrets or install competing proxy stacks.
- [ ] Prove full integration: selected node physically changes and ChatGPT public probe succeeds, then app diagnostics recover after fresh client events.
- [ ] Human visual acceptance of menu recovery state and action.

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
