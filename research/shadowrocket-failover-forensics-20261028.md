# 2026-10-28 · Shadowrocket / TunnelSentinel 故障转移证据复核

**取证窗口：** 2026-10-28 00:00 至约 10:40（Asia/Shanghai）；实机 Mac-mini.local。只读扫描当日 Guardian 日志、workflow_timeline、Codex 本地 SQLite 结构化事件、2026-10-26 最后一次原生规则审核和当时运行状态。**未切换节点、启用代理功能、重启服务、登录业务或生成内容。**

## 1. 关键时间线（采样，不是精确业务停机）

| 时间 | 代理公共入口/出站证据 | 同时间客户端业务证据 |
|---|---|---|
| 03:23:29–03:23:44 | 公共 GET 采样超时，约 14.3s 后采样恢复；03:24:18 出口 FRA→LHR | 未找到这段的明确 Codex 响应流失败 |
| 04:20:09–04:21:06 | 连续 4 个约 14–15s 采样失败，约 56.6s 后采样恢复；04:21:40 出口 LHR→ICN | 04:20:09 ChatGPT thread catalog 同步异常；04:20:38 Codex Remote Control 重连，约 04:22 恢复 |
| 05:01:21–05:01:35 | 单次公共采样失败；恢复不伴随出口变化 | 未确认同窗口实际业务失败 |
| 09:24:07 | 没有同时段公共入口超时 | Codex `broken pipe` 一次，随后 09:24–09:29 有多个真实 WebSocket 建连日志（不能证明完整任务成功） |
| 10:17:31–10:17:46 | 单次公开入口探测异常 | 10:17 Codex remote-control 曾有断线/重连事件；不能仅凭相近时刻证明同因 |
| 10:23 与 10:30 | 公共采样短暂异常，恢复约 11–12s | 没有足够证据认定某实际节点不可用 |

**关键限定：** `sampled_outage_s` 反映 Guardian 采样窗口；不是真实业务停机秒数，也不是 Shadowrocket 原生失败计数。

## 2. 全局节点观察 vs 公共出口

Guardian 在 00:00–09:52 全局选择标签为 `USA Seattle 05`，而公共出口依次跨新加坡、法兰克福、伦敦、首尔。09:53 看到全局标签 `Seattle 04`，10:21 为 `Seattle 07`，10:31 为 `Japan 10`。标签转变可能来自用户、软件或其他控制层；无法凭名称断定。出口发生 6 次以上变化同样不能证明分组自动故障转移：存在同一节点上游多出口、代理规则路由、备用路径等其他解释。

最新 native proxy request reader = disabled；`native_group_route_verified=false`；没有 Shadowrocket 对「命中 OpenAI 规则的单次请求」所选具体节点的实时只读证据。因此 **禁止把历史公共出口或全局节点当成真正 GPT per-node 路由归属，也不能对 Seattle 04/05/07、Japan 10 做真实可靠性排名**。样本长度不一致，且缺乏每节点业务成功因果对应。

## 3. 原生 Shadowrocket 机制准入

10 月 26 日 21:51 的最后一次规则测试：`chatgpt.com`、`ws.chatgpt.com`、`api.openai.com`、`desktop.chat.openai.com` 均命中 `PROXY`，没有确认直接命中 `OpenAI-Resilience`。该结果已有约 37h，必须重新核准。当前 `native_fallback_enabled=true` 只是 TunnelSentinel 对历史组的配置声明，`native_group_route_verified=false`，不能证明原生组正接管 ChatGPT。

Shadowrocket 文档区分（1）组内 `fallback` 按最近一次测试结果选择可用候选，（2）「全局路由→启用回退」对连接失败进行回退，文档称连接失败 3 次触发，节点仅要求可用且不按延迟排序。前者只有被实际规则引用才真正参与选路；后者对 PROXY 策略可能跨全部首页节点选取，业务能力不可保证。参见 https://github.com/LOWERTOP/Shadowrocket/wiki 。

本机经 **当前系统代理** 且不带凭据测试：`https://chatgpt.com/cdn-cgi/trace` 的 GET=200、HEAD=403（curl 18）；`https://chatgpt.com/robots.txt` 的 GET/HEAD 均 200；`https://www.gstatic.com/generate_204` 的 GET/HEAD 均 204。**不能推断 Shadowrocket 背景自动分组到底使用 GET 还是 HEAD**。测试 URL 只能证明公开网页传输，不能保证 WebSocket 长流/已登录业务完成。暂不改任何 URL/间隔/启用回退。

## 4. 可执行的安全顺序

1. **最先消除 L0 阻塞**：在 Shadowrocket「配置 → 测试规则」重新核准三项 OpenAI 核心域名当前命中策略，确认活动配置、是否实际引用 `OpenAI-Resilience`。操作仅做单次只读规则检查，不改变选择。
2. **确认组自身设置**：组类型 `fallback`、绑定订阅和候选范围、是否启用测试、自动测试的 URL/方法/间隔/超时，另查全局「启用回退」真实状态。区分是否希望仅 GPT 专用回退，避免随机切到不支持 GPT 的首页节点。
3. **真实请求归属**：优先由 Shadowrocket 自身「数据→代理」的原生界面手工查看一次已发生的 OpenAI 请求匹配策略和实际节点。没有授权后台读取接口，禁止访问受保护的 App Group 原始订阅数据库或隐式改变权限。
4. **业务验收/故障相关**：把上述节点归属与同段 Codex 真实响应流错误、Remote Control、ChatGPT 业务成功/失败关联起来；只有多个独立候选带可靠样本，才启用项目已有 `gpt_node_business_ranker.py` 试用推荐。公共延迟、出口归属以及 GET200 **不能**当作“推荐此节点”。
5. **自动切换审批**：先核准原生组故障转移与当前业务规则，观察真实自动改选、读回实际请求归属与业务恢复，再考虑有保护阈值/冷却的 TunnelSentinel 自动写策略。当前一切自动节点写控制仍保持 OFF，不进行无网/断线故障注入。

## 5. 实现成果与限制

新增只读脚本 `scripts/shadowrocket_failover_preflight.py` 读取现有 status、config、规则审核及守护日志，输出阻塞原因（例如 `rule_audit_missing_or_stale`）与当天采样统计；**不会读取用户会话、节点凭据、Shadowrocket 私有数据库，也不操作代理**。配套单测覆盖旧审核、PROXY 误当组、全局节点误当业务节点、候选证据不足等 fail-closed 逻辑。

**当前结论：** 04:20 的跨层故障确有较强关联，值得优先验证原生故障转移；但截至本次取证，无证据足以证明 Shadowrocket fallback 已在当时选路，也无依据准确命名一个值得手动切换的候选节点。下一步的关键不是再扫延迟，而是当场核验活动规则和实际每请求节点归属。

### 2026-10-28 10:49–11:00 · 三步实机执行补充

1. **真实执行了现有 Mac App“节点 → 核验 Shadowrocket 当前配置规则”**，状态文件写入 `partial_rule_matches`，规则数 0，时间 10:49:58。不是“PROXY 没命中”，而是核验器未可靠进入 Shadowrocket「测试规则」页。随后单窗口截图确认实际仍在 Shadowrocket「首页」，旧版 `prepare()` 误以任何 `AXTextField`（包括首页搜索栏）为测试规则输入。切换前用户当前全局节点不变，系统代理仍由 Shadowrocket 持有。
2. 进一步 AX 实机读取当前窗口仅显示 0 个完整子元素，macOS Quartz 屏幕合成观察到应用缩略窗口（不同于逻辑 AXWindow 大小）；无法在不强行切换桌面/绕过 TCC/读取私有数据库的情况下完成 fallback 组页面核准。**本轮不声称组类型、全局“启用回退”、测试 URL 或业务路由已验。**
3. 修改 `menubar/TunnelSentinelShadowrocketAudit.swift`：测试页专属标签 + 非搜索输入框双重门槛；未验证则拒绝输入。修改 `menubar/TunnelSentinelMenu.swift`：仅四条完整真实规则能刷新正式审计，否则写独立 `shadowrocket_rule_audit_last_attempt.json`（仅失败状态、时间、条数）、显示原因，不覆盖有效历史核验。该次旧版已经覆盖 10/26 旧审计，这是已发生的现场操作，不能假称旧详细数据仍在。
4. 修复 `scripts/shadowrocket_failover_preflight.py` 的条件分支：本次刷新但空结果应为 `rule_audit_incomplete_or_unavailable`，不应误报「已证实规则没有匹配组」。配套回归覆盖空结果。现仍无真实单请求的节点归属、当前完整组成员、可比业务成功；`manual_node_recommendation=null` 是正确的保守结论。
5. 仍需一次 Shadowrocket 测试规则窗口对四域名完成读取，以及在 GUI 原生只读检查 fallback/全局回退状态；不能通过手动改规则、切节点、读取被 macOS 保护的 App Group 数据代替。对节点推荐只使用实际分流归属 + 业务成功/断流的同源证据，不作“Seattle04/05/07/Japan10 最优”断言。
