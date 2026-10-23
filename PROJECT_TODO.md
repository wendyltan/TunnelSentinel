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
- [x] v1.5.3 将「事件日志」改为节点优先视图：按证据区分实时未知节点名、最后一次用户界面确认的 Seattle 05（日期及来源）、候选节点清单、全局手选节点、现有出口地区和两次成功采样的历史；保留原始日志视图。
- [ ] **真正实时节点名**：调查 Shadowrocket「数据 → 代理 → 启用日志记录」的原生日志或导出是否含每条 ChatGPT 请求实际节点名称。仅在用户知情的可脱敏样本验证字段且有受支持的只读接口时接入；不默认开启可能记录 URL 的全量代理日志。
- [ ] **换订阅健康告警**：原生组订阅绑定单一记录，换机场需要重绑定且当前按精确名称筛选可能为空。仅当有可靠的只读订阅/候选元数据访问方式时，自动检查订阅迁移、空候选和正则命中数，不得擅自读取私密订阅 URL 或写 Shadowrocket 内部数据库。
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
- [x] **逐节点 ChatGPT 智能选择可行性研究**：确认原生 `fallback` 可逐候选检查单 URL；当前 Mac 实测 `GET /cdn-cgi/trace=200`、`HEAD /cdn-cgi/trace=403 (Cloudflare challenge)`，而 `HEAD /robots.txt=200`；自动分组是否同用 HEAD 尚待原生测试证实。见 `research/chatgpt-node-eligibility-20261023.md`。
- [x] v1.5.1 增加可选、低频的 **当前路径** GET/HEAD Cloudflare 差异检测与菜单提示，默认关闭，独立于节点轮换；全量回归修复旧用例直接读取 macOS 受保护节点状态的权限问题。
- [ ] **新 P0 — 核实原生 fallback 的实际后台测试方式 / 降低假失效风险**：实机 Shadowrocket 2.2.92 “延迟测试方法”目前是 **TCP**（不是 CONNECT/HEAD），手动点“代理分组 → 测试”的结果和自动分组后台测试彼此独立。不能再以手动测试结果推断后台请求方法；需应用提供可信后台测试证据或厂商确认后，再考虑调整活动测试 URL。当前路由保持原样。
- [x] Shadowrocket 组内 UI 人工验收：四个候选 `USA Seattle 05 (108ms，当前勾选)`、`USA San Jose 07 (263ms)`、`Japan 04 (110ms)`、`Japan 14 (107ms)`；“根据 Ping 排序”和“测试并选择最快服务器”都关闭。人工测速不会自动选择最快节点，但仍不能证明后台自动策略的 HTTP 请求方法。
- [x] v1.5.2 新增自然故障留证：通过原有 ChatGPT 公共探测，连续两次健康样本确认出口 IP 变化，记录最近 6 次及附近是否有入口中断；只能证明出口变化，不能冒充订阅节点切换。
- [ ] 下一轮验收：结合自然故障时的 `egress_change_history`、`last_public_edge_incident` 与客户端业务异常复盘；如需人为测试后台 fallback 方法，必须得到原生后台诊断/厂商证据，不能靠手动 Ping 推断。
- [ ] **更高级的智能选节点仍未完成**：只有拿到可信的逐节点后台健康与节点标识，才可能把客户端真实业务错误归属到某一候选；先复用原生组测试，不依赖 Nexitally 页面来推断每个节点的解锁能力。不支持的公开 API 不得编造或用第二套代理内核替代。

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
