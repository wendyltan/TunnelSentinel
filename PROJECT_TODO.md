# TunnelSentinel — outstanding acceptance

## P0 · Proven autonomous recovery (OPEN)


- [x] 2026-10-25 v1.5.5：将 Codex 原生 SQLite 的 Broken pipe、WebSocket 握手失败、连接重置接入业务状态（与公共入口健康独立），已通过 69 项回归并实机报告错误；不因流式错误盲目切换。
- [ ] Codex 流式故障驱动的分组级安全切换：先获得受支持的 Shadowrocket 分组节点控制接口以及候选业务稳定性证据；目前原生 fallback 仍按公共 URL 首个可用选择 Seattle 05，不能用无凭据 HTTP 200 代替真实 Codex 流式运行检查。自然故障观察，不人为断网。

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
- [x] **OpenAI 原生节点日志接入**：用户截图及 Mac 本地只读 SQLite 查询证明原生 proxy 日志的 `result` 包含 `OpenAI-Resilience # 🇺🇸 USA Seattle 05`。v1.5.4 用隔离的超时子进程读取，精确过滤 OpenAI 域名与分组，只保留真实请求节点+时间+域名；历史节点变化与出口变化分开展示，超过 10 分钟无新请求即降级为上次记录。不自动开启/关闭 Shadowrocket 日志。
- [ ] **macOS App 数据权限验收（需要用户选择）**：v1.5.4 独立进程只读 SQLite 已通过，交互式读取可识别 Seattle 05，但后台 LaunchAgent 被 App Management 权限阻塞，2.5s 后超时；已暂停连续读取，菜单退回带来源日期的上次节点。用户可审慎决定是否授权较广的 App Management，或后续实现 NSOpenPanel 选择 Shadowrocket Logs 文件夹的显式授权方案，不绕过 TCC。
- [ ] **真正不间断的“后台当前选中节点”**：仅依赖原生请求日志可确认“最近一次请求的节点”，并不能在没有新请求时证明原生 fallback 此刻选中谁。若 Shadowrocket 后续提供官方只读当前分组后台 API，再升级到严格的实时状态，不能伪称日志即内部状态。
- [ ] **换订阅健康告警**：原生组订阅绑定单一记录，换机场需要重绑定且当前按精确名称筛选可能为空。仅当有可靠的只读订阅/候选元数据访问方式时，自动检查订阅迁移、空候选和正则命中数，不得擅自读取私密订阅 URL 或写 Shadowrocket 内部数据库。
- [x] **首条真实的被动故障/出口事件**：2026-10-23 19:09:21 记录公共入口约 16.9 秒中断后恢复，19:10:23 经两个连续健康样本确认出口从 US-SEA 变为 US-SJC；业务层目前正常。但不等于已验证 Seattle 05 → San Jose 07 的实际节点切换。
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

### 2026-10-25 业务流中断触发自动故障转移（进行中）
- [x] 已确认实际可编辑控制面：Shadowrocket 原生 `OpenAI-Resilience` 分组的候选 regex，而非无效的全局节点按钮
- [x] 实现独立 210 秒内 3 次 Codex 错误触发、重复去重、10 分钟冷却、每日上限、阶段闭锁及网络失效单次回退
- [x] 原生 macOS 有界控制器、组名/原 regex 校验、保存后重读校验，独立签名应用安装
- [x] 部署 45 秒 LaunchAgent，开关默认 OFF，保持现有 Shadowrocket 和 Codex 正常工作
- [ ] **P0 人工一次性授权**：macOS 隐私与安全性 → 辅助功能 → 允许 TunnelSentinel Route Controller；验证独立签名 App 作为后台进程可完成有限 8–12 秒的只读 UI 探测，且不再出现剪贴板/TCC 等待
- [ ] P0 授权成功后开启 `codex_auto_failover_enabled`，仅在自然业务故障发生时启动分组级候选排除；对比原生 PacketTunnel group tester 与 Codex 流式恢复结果
- [ ] P1 从原生可信状态获取自动切换后的 backend 验证，确认后才允许进一步候选排除；若不得已回滚，优先保障基础链接并报告不可验证状态

- [x] 2026-10-25 后台权限分离实测：交互式签名 App 权限检查成功；同一 App 从 GUI LaunchAgent 启动时返回 `ACCESSIBILITY=required EVENT_CONTROL=required`。支持无 UI 的 `--check-permissions`。

- [ ] **2026-10-25 17:17 授权后验收仍未过关**：交互式权限已变成 granted；独立 `--probe` 依旧焦点丢失/8秒超时；全量 AX 属性查询仍不稳定。现有 GUI 控制器不能在后台安全修改分组。需要打开 `OpenAI-Resilience` **编辑页**进行只读、定时验收，不能直接开启 `codex_auto_failover_enabled`。
- [x] 控制器源代码取消剪贴板读取和写入，使用辅助功能 `AXFocusedUIElement / AXValue` 读写并设置消息超时（源码已编译，但因尚未完成真实 UI 验收未部署签名 App）。


### 2026-10-25 晚间 · 自动恢复最终控制器与签名验收
- [x] 直接 AX 读取 `OpenAI-Resilience` 原生当前组内节点、筛选规则和保存动作；不使用剪贴板/固定坐标
- [x] 保存原规则不变→关闭弹窗→自动重新打开→确认已持久化；验证对话业务基本链路仍正常
- [x] 自动引擎按原生**当前实际节点**排除，最多排除两个节点、保留至少两个候选，10分钟冷却并在旧修改未验证时停止升级
- [x] 完成 85 项回归，新增后台预检“不写配置”测试；稳定 Apple Development 签名的控制器 0.2.0 已安装
- [ ] **系统授权（仅用户可做）**：现存辅助功能开关仍对应旧临时签名版，LaunchServices 启动签名新版报告 ACCESSIBILITY=required；必须为当前 `~/Applications/TunnelSentinelRouteController.app` 重新授权
- [ ] **P0 后台真正启用**：授权后在 LaunchAgent 身份完成无写权限读测，再启用 `codex_auto_failover_enabled`，自然故障时验证新节点实际生效，跟踪 Codex 流式稳定性
- [ ] **P1 强化无需前台界面场景**：当前原生辅助功能控制依赖 Shadowrocket 原生分组列表/编辑页，切到其他页面或锁屏时不能保证自动编辑，需支持受限导航或其他官方接口，绝不可假报恢复

- [ ] **真实 macOS TCC 归因问题（2026-10-25 18:48）**：后台 Python → 已签名原生控制器会把辅助功能请求归因给责任进程 Python3（不能为了此功能给整个 Python 扩权）。直由 launchd 启动控制器时系统正确识别签名 Bundle ID，但仍显示 `authValue=0`；系统弹出 TunnelSentinelRouteController 辅助功能申请提示，尽管设置页同名开关呈蓝色。需要用户在弹窗选择「打开系统设置」，对**当前**已签名 App 的开关关闭再开启，确认真后台 `granted`。若通过，优先改为由原生 signed controller 直接拥有后台辅助操作，而非由 Python 子进程发起。

- [x] 后台 Python→控制器的 TCC 归因问题已通过正式 `launchctl submit` 架构消除，macOS 识别请求者为控制器自身；87 项回归通过，已部署只读监测
- [ ] **当前唯一权限阻塞**：系统设置蓝色 `TunnelSentinelRouteController` 条目在 Apple `tccutil reset` 该 Bundle ID 后仍保留，极可能是旧可执行文件的路径授权。需用户在系统设置中选中该条并点底部「−」移除，再通过「+」选中整个 `~/Applications/TunnelSentinelRouteController.app`，而不是内层 `Contents/MacOS` 二进制，开启授权
- [ ] 授权后用真正独立 `launchctl submit` 验证 ACCESSIBILITY 与 EVENT_CONTROL 均 granted，再依程序默认安全模式开启自动转移；必须观察原生节点变更与 Codex 业务成功，不能把编辑成功当成业务恢复
