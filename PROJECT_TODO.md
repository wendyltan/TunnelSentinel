# TunnelSentinel — outstanding acceptance

## P0 · Proven autonomous recovery (OPEN)

- [x] Stop looping over stale subscription names; use recently successful verified candidates.
- [x] Shorten degraded detection checks without changing normal network checks.
- [x] Do not auto-rotate from mere 429/Cloudflare client diagnostics.
- [x] Verify selection and a fresh edge request before declaring recovery; classify selector failure and back off.
- [x] Menu displays recovery failure and offers open-Shadowrocket action.
- [x] 菜单栏实时文字与主面板右上角徽标使用同一状态来源（系统菜单栏实时可访问性确认成功；用户视觉验收仍待执行）。
- [x] Shadowrocket 原生 `fallback` 方案与独立示例片段完成，保留现有 Config 规则，未改动运行配置。
- [x] **真实原生 fallback 已启用**：用户在 `sr_cnip-copy.conf` 中绑定订阅并保存 `OpenAI-Resilience`；本次通过 GUI 将已有 OpenAI rule-set 改为 `OpenAI-Resilience` 并启用测试副本，保留原 `sr_cnip.conf`。
- [x] Shadowrocket 的“测试规则”实测：`chatgpt.com` / `ws.chatgpt.com` / `api.openai.com` 都走 `OpenAI-Resilience`、当前显示 `USA Seattle 05`。
- [x] 测试副本切换后 ChatGPT 公共入口连续返回 HTTP 200，无需更改原始订阅。
- [x] Guardian 新增 `native_fallback_enabled`，在原生接管时不再发起旧 URL 节点轮换，并明确全局节点不等于 OpenAI 实际出口。
- [ ] **P0：失效切换真实验收**。尚未故意使当前出口失效以验证自动改选、恢复耗时及客户端 WebSocket 稳定性。需安排经过许可的可回退故障注入；平时监控不等于此验收。
- [ ] 长期检查 ChatGPT 客户端、Codex 连接的错误收敛与反复切换风险。
- [ ] Human visual acceptance of menu recovery state and action.

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
