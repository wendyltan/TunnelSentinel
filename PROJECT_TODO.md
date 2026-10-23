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
- [x] 面板及菜单栏双路状态：OpenAI 真实出口样本（通过已有 ChatGPT 公共探测响应获取的 IP/colo）＋ Shadowrocket 全局手选节点。UI 明示实际订阅节点名尚无可持续读取的可信来源。
- [ ] 若 Shadowrocket 后续提供只读、可验证的分组后端名称 API 或代理日志接口，用实际节点名替代出口地区，严格标记时间和缓存失效；不要通过写死 Seattle 05、扫描订阅密钥或频繁打开 GUI 来伪造实时值。
- [ ] **P0：失效切换真实验收**。尚未故意使当前出口失效以验证自动改选、恢复耗时及客户端 WebSocket 稳定性。需安排经过许可的可回退故障注入；平时监控不等于此验收。
- [x] 将 Mac 客户端实际 `Thread catalog sync failed`（已见 HTTP 403）加入独立的会话同步告警；公共探测仍不据此自动轮换节点。
- [x] 对照 OpenAI 官方清单完成第三方 OpenAI 规则集静态覆盖核查：识别 `oaistatsig.com`、`openaimerge.com` 两个 OpenAI 独有域名遗漏，准备未启用的安全补充片段，并区分共享 Cloudflare/WorkOS 域名风险（`research/openai-route-and-failover-audit-20261023.md`）。
- [x] 守护后台增加被动公共入口故障/恢复留证，不把出口变化伪称为 Shadowrocket 已切换节点，不重启 ChatGPT/Shadowrocket。
- [ ] 使用 Shadowrocket **测试规则**逐项核实 `desktop.chat.openai.com`、`challenges.cloudflare.com`、`auth.openai.com`、WorkOS 及 WebSocket 域名是否按预期分流；确认必要性后，使用 App 原生编辑器应用最小补充片段。仅凭匿名 curl SSL 错误不能判断登录会话真实路由故障。
- [ ] 长期检查 ChatGPT 客户端、Codex 连接的错误收敛与反复切换风险。
- [ ] Human visual acceptance of menu recovery state and action.

- [x] Nexitally AI Trace 检测方法核实：网页在当前访问者网络即时执行每域 `/cdn-cgi/trace` 与 GeoIP 查询，不提供每节点历史测试数据接口。
- [x] 新增独立、低频 AI 多站点检测（8 个公开域名，每约 15 分钟，仅 HTTP 200 + 有效出口 IP 记为公共可达）；不阻断基础心跳，不读取订阅私密信息，结果过期后撤回。
- [x] 菜单栏新增「AI 分流检测」可读摘要和逐站点结果，保留现有原生 fallback 节点切换权。
- [ ] **更高级的智能选节点仍未完成**：若服务商未来有明确、可验证的单节点检测数据 API，或者 Shadowrocket 提供可靠的逐节点检测/选路接口，再做动态候选过滤及实机切换验收。不能把当前浏览器公共站点检测误称作逐节点解锁能力。

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
