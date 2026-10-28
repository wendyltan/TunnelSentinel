## 最新架构：2026-10-25 · 只保留 TunnelSentinel.app

- [x] 移除独立 `TunnelSentinelRouteController.app` 的用户可见安装（旧版保留备份），停用并移出独立 `tunnelsentinel-autofailover` LaunchAgent
- [x] `TunnelSentinel.app` v1.6.0 稳定签名；在菜单栏同一 Swift 进程内集成节点 AX 控制与恢复轮询
- [x] 菜单栏提供节点故障转移状态、开启/关闭入口；Guardian Python 只读 Codex 业务日志，永不作为 AX 守护责任进程
- [x] 87 项 Python 回归通过；Shadowrocket VPN/规则未被强制切换
- [ ] **P0 只需授权 TunnelSentinel 一次**：系统设置 → 隐私与安全性 → 辅助功能 → `~/Applications/TunnelSentinel.app`；当前内置自检状态 `authorization_required`
- [ ] **P0 完整自动恢复实机验收**：自然 Codex broken pipe 达到阈值后，检查 AX 规则持久化、原生组节点切换、真实 Codex 流恢复；不人为断网
- [ ] P1 Shadowrocket 不在原生代理分组界面或 Mac 屏幕锁定时的无 UI 自动控制能力尚未实现；可靠失败关闭并提醒用户

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

### 2026-10-25 Clash Verge adapter / 自动故障转移 P0–P1
- [x] 当前系统代理独占判断：与 Mihomo live mixed-port 比对，私有 Unix Socket 控制器，无额外 TCP API 或管理权限
- [x] Guardian 动态切换代理探测，Clash 接管时阻断 Shadowrocket 传统重连和原生 UI 节点改写；返回旧端口须证据匹配
- [x] OpenAI 请求连接链、AI→Proxies 策略、候选动态发现及仅最近运输延迟评估；避免历史出口 IP 冒充节点
- [x] 菜单栏 Clash 监测与自动恢复模拟模式；AI 共享组当前绝不真实自动切换
- [x] 运行时部署与隔离测试，包括 API 失联和选路归属丢失；保留一个菜单栏 App
- [ ] P0：在不活动配置副本中设计 `OpenAI` 专用策略组，检查 GPT/Codex 域名路由覆盖与对非 GPT 流量的影响；不得直接改写当前订阅
- [ ] P0：选择节点健康证据策略（静态 GET/HEAD 与真实 WebSocket 区分），失败隔离与自动恢复；模拟连续故障、重复触发、睡眠/唤醒
- [ ] P1：补充可撤销的受控组内真实切换、候选 API readback 与故障回滚，在 user-approved 维护窗口做首次真实验收
- [ ] P1：确认 macOS 关闭系统代理、改开 Clash TUN、或重新切回 Shadowrocket 后的恢复流程；当前仅识别系统 HTTP(S) 代理接管
- [ ] 用户视觉验收：Clash 节点显示、来源可信度、宽度 340pt 的菜单栏布局

### 2026-10-26 Clash 真正自动故障转移
- [x] 建立独立 `TunnelSentinel-OpenAI` 组和优先域名分流，避免改动共享 `Proxies`
- [x] Mihomo 真实重载、控制组回读、ChatGPT 请求链核实
- [x] 真实切换 Japan 02 并安全恢复原节点的 canary 验收
- [x] Codex 新鲜流错误触发守护调用、限频/隔离/每日阈值及原生 API 只写专用组
- [x] 生产模式已启用，单独菜单开关可关闭与重启监测服务
- [ ] 在下一次**自然发生的 Codex Broken pipe** 事件中验收实际故障恢复和登录后流式业务成功证据；当前只证明路由层与公共出口
- [ ] 不同订阅自动更新／订阅更换时确认 Clash Verge 增强配置重建过程，验证对缺失成员 fail-closed 的提示
- [ ] 睡眠/唤醒和锁屏下自动切换端到端验证；持续记录节点变更和真实业务成功率

## 2026-10-26 P0/P1 稳定性修复验收（此处为当前基线；上文旧版本 TODO 保留作历史）
- [x] 统一 `automatic_control_enabled` 总闸门，生产设为 `false`；两套节点切换旧标志均关闭
- [x] `tunnel_recovery_enabled` 独立开关，生产设为 `false`，断开网络不自动重新启用 Shadowrocket
- [x] 明确只读模式状态 `proxy_control_mode=read_only`，健康恢复不再冒充节点切换成功
- [x] Shadowrocket 旧分组仅标为“历史配置 / 当前未核实”，不用配置名冒充实际规则命中
- [x] 纯日志分类：`ResizeObserver` 布局警告不再计入业务异常；新增浏览器后端请求失败分类
- [x] 公开入口 / WebSocket 握手 / API TLS / 登录 TLS / 桌面 TLS 分层探测，固定域名、无账号凭证、每 300 秒运行，不触发自动切换
- [x] Codex 只读 SQLite 流断线保持独立观察；菜单提供分层诊断与两个开关
- [x] 历史独立 Route Controller 安装器和旧 Swift 分组编辑器移入 `legacy/`；不影响当前单 App
- [x] 回归单测、Swift 类型检查、签名和当前 Shadowrocket 网络实机检查
- [ ] P1 · Computer Use 真正业务验收与被动监控：建立受信任的「单次工具执行结果」只读事件源（明确成功 / 失败 / 时间戳与来源）；普通非 ChatGPT 网站的真实浏览器执行与事件关联。当前仅有 SkyComputerUseService 进程、Codex IAB startup-ready、ScreenCaptureKit 初始化活动及异常日志，无操作完成回执；这些就绪/传输事件不能升级为业务成功或据此自动切换代理。监控中心建议分列「控制后端就绪」和「真实操作结果（尚未验证）」，避免用户成功操作后误读 unknown 为未运行。
- [ ] P1 · 下次订阅实际更换时验证组绑定、规则匹配和 Shadowrocket UI 状态；当前无法通过公开 API 保证自动重绑定
- [ ] P1 · 无需前台界面的 Shadowrocket 组读取和锁屏切换仍不可用，禁止标为已交付
- [ ] P1 · 出现真正的 Codex websocket 业务故障时交叉核对 SQL 日志、TLS/WSS 探测与浏览器后端日志；公开 200 不等于业务可用

### 2026-10-26 UI v2
- [x] 340pt 精简主菜单、监控中心单入口、原生 NSSwitch 两项控制
- [x] 分层诊断、AI 分流、节点事件集中到四标签结构化窗口，取代长文本弹窗
- [x] 未验证 Shadowrocket GPT 分组移除主界面常驻占位，主信息只显示公共出口与只读模式
- [x] 用户当前 Shadowrocket 无可靠分组级 AX 数据，不再显示“等待读取”；单独解释信息来源与可用限制
- [x] 5 秒状态刷新保持监控中心当前滚动位置；标签切换恢复顶部
- [x] Mac 实际打开各 UI 标签截屏，并通过 Python 回归与 Swift typecheck
- [ ] 尚未完整验收的功能仍包括锁屏原生节点探测、订阅迁移、已登录的 Computer Use 实际网页操作；不可用功能继续保持不可操作

### 2026-10-26 21:07 · 设置响应性和探测协议
- [x] NSSwitch 配置更新改后台、限时重载，杜绝等待 launchctl 阻塞 AppKit 主线程
- [x] 开关显示从配置实时读取，防止 Guardian 状态延迟导致“回弹”；保存过程中拦截重复提交
- [x] 官方 ChatGPT 与 Codex WebSocket 目的地域名分别测试，展示实际模拟 HTTP GET / Upgrade 方法
- [x] WebSocket 只有 HTTP 101 为真正握手成功；403/404/421 属于 HTTP 有响应、业务升级未验
- [x] 显示请求层级：公开 GET / 根路径不等于已登录业务 API，请勿混淆 TLS 探测与真实 Computer Use
- [ ] 需用户在正常工作时观察下一次 NSSwitch 实际点击体验；本轮不为模拟卡顿故意反复开关隧道重连
- [ ] 需后续有获授权的业务级测试证据才能标记实际 Codex 长流、Computer Use 为成功

### 2026-10-26 21:25 · 真业务证据与规则读取
- [x] Codex 30min 已发生的允许列出后端 GET/POST、状态码和真实 WebSocket 成功连接事件，纯本机只读元数据聚合
- [x] AI 分流读取改走 Shadowrocket 官方原生「测试规则」按需核验，避免硬编码 AI 组与机场节点，最多 10min 作为近期证据
- [x] 主窗口移除重复“检查链路”，移除 Shadowrocket 无效“GPT 实际请求节点”的空卡
- [x] 边界：不会读取密钥、原生 App 私有容器，不会无用户点击后台操作 Shadowrocket UI，不会自动修改代理
- [ ] 用户实际点击新“核验规则”按钮后检查 macOS Accessibility 授权和操作焦点恢复行为
- [ ] 切换 Shadowrocket 规则配置与更新订阅后进行第二次测试，确认动态策略匹配内容变化，不能把上次核验冒充实时请求
- [ ] 未来若 Shadowrocket 提供可信只读 API/请求日志适配，再增加后台实时客户端请求节点识别（目前无）
- [x] 签名 App 中实机点击新原生规则核验、生成 4 域名 PROXY 证据并检查可读卡片截图
- [x] 当前 Shadowrocket 系统代理、自动节点开关、隧道重连设定均未修改；源测试和签名核查通过

### 2026-10-26 P0 实施 / 真实业务状态 + 故障时间线
- [x] Guardian 统一 `workflow_health` 四轴状态、证据等级、采集时间，未知不当作绿色
- [x] 当前代理与公共入口失败时 ChatGPT 不会继续使用前一次成功探测显示正常
- [x] `workflow_timeline.json` 本地事件持久化、按日志事件时间去重、七天滚动、两轮正常才关闭事故，重启不丢
- [x] 只收集允许列出的网络/客户端元数据，不保存身份头、正文、原始 IP 或私人链接
- [x] 故障期间仍限流运行分层诊断；无代理监听时异步发起有限检测
- [x] AppKit `launchctl` 服务检查不再同步阻塞主线程，改低频后台缓存；移除无工作的高频节点轮询
- [x] 监控中心概览四轴状态、时间线置前；保留原只读规则匹配及节点开关配置
- [ ] 手动真实 Computer Use 普通网页动作验收、图片上传、长时 Codex 任务；未获业务成功事件不得标为成功
- [ ] 将设备睡眠/唤醒及系统网络服务变动纳入宽限/异常隔离测试（当前不擅自触发断网）
- [ ] 后续考虑事件导出和历史趋势图；不得让轻量监控演变成第二个代理内核

### 2026-10-27 · 监控中心视觉 V3
- [x] 五标签信息架构按「总览→时间线→诊断→节点→设置」排序
- [x] 总览健康摘要与 2×2 原生紧凑状态卡，保留证据等级
- [x] 断线事件按日分组；远程控制周期合并与可展开详情
- [x] 技术日志、节点规则、设置从日常事故列表剥离
- [x] Swift 类型检查与 Python 回归，签名 App 实机打开并截图核对
- [ ] 候选增强：按需查看 24h/7d 的真实事件统计，须在足量数据时才开放


### 2026-10-27 · Impeccable 监控中心 V4
- [x] Impeccable + frontend-design 原生视觉重审：移除四张均质卡片，四服务合为一个信息面板
- [x] 总览移除显眼的常驻滚动条，首屏完整阅读；长页保持 macOS 原生 overlay 滚动
- [x] 撤下所有没有真实业务能力支持的推荐、测速导入、等待候选提示和快捷入口
- [x] 保留可用的 Shadowrocket 当前规则核验、全局节点、公共出口与客户端事件
- [ ] 无扰动 GPT per-node 业务验证：缺少当前 Shadowrocket 官方可验证接口，未上线任何推荐

### 2026-10-27 · 跨代理软件通用健康检测
- [x] 实际确认端口 7890 经当前代理到 ChatGPT HTTP 200，旧 1082 关闭导致假离线
- [x] 每个 Guardian 周期解析 macOS 实际 HTTPS/HTTP/SOCKS 代理，不再硬编码 Shadowrocket 探测端口
- [x] direct/TUN 无显式代理时直接做当前网络出站检测
- [x] PAC/自动发现不可靠解析时显示 unknown，避免伪造连接失败
- [x] 切换代理自动隔离旧失败计数、Shadowrocket 节点信息与异步深层/AI 探测历史
- [x] 原生 GUI 支持通用代理的实际端口显示，其他代理下隐藏 Shadowrocket 专用规则操作
- [x] Shadowrocket 自动节点开关保持关闭，原隧道重连设置保留但不得用于其他代理
- [x] Python 全量回归、Swift 类型检查、签名 App 实机部署、节点/总览截图
- [ ] PAC / 自动发现按实际目标域名使用 CFNetwork 解析；当前标示待确认，不冒充真实结果

### 2026-10-27 · Computer Use 本机观察独立修复

- [x] 新增只读本机 Computer Use 工具调用元数据采集，严格区分进程在线、后端就绪、工具调用结束、真实业务目标成功
- [x] Guardian 异步、限时采集并展示来源/时间/失败，过期失效；不把工具调用完成判成最终成功，不参与自动节点控制
- [x] 总览按当前工作使用优先级调整为 Computer Use → Codex → ChatGPT → 基础网络；辅助节点/匿名深层探测移至诊断页
- [ ] P1 · 与用户新一次 Mac 本机 CUA 动作实时对照，验证本机工具执行事件进入总览/时间线；当前晚间云端/其他工具链的动作尚未确认是否能记录
- [ ] P1 · 寻找官方可授权的 ChatGPT 云端 Computer Use 最终结果回执；若无法获取，不通过读取私密消息、抓包或合成 HTTP 模拟成功
- [ ] P1 · Codex 完整生成、ChatGPT 已登录成功回复的独立结构化回执（目前公开 GET、模型目录 200、WS 建连仅作为部分证据）

### 2026-10-28 · 今日故障转移证据与下阶段准入

- [x] 实机只读关联 Guardian 公共探测异常、Codex broken pipe/Remote Control、ChatGPT thread sync、全局节点与出口变化，形成 `research/shadowrocket-failover-forensics-20261028.md`
- [x] 添加只读 `scripts/shadowrocket_failover_preflight.py`：严格拒绝过期规则审计、`PROXY` 错当 `OpenAI-Resilience`、全局选中节点和公共出口冒充 per-node 路由证明；无可靠来源时手动节点推荐返回 null
- [ ] P0 · 在不改路由的情况下使用 Mac App 已有 Shadowrocket「测试规则」动作对当前配置重新核对 `chatgpt.com`/`ws.chatgpt.com`/`api.openai.com`，确定实际命中的是 `PROXY` 还是 `OpenAI-Resilience`；审计应带现时来源和有效期
- [ ] P0 · 通过 Shadowrocket 官方界面确认「启用回退」真实状态、OpenAI 代理组具体绑定规则/订阅、候选数、自动测试是否启用、测法/URL/间隔；不要把 TunnelSentinel 的 `native_fallback_enabled=true` 配置视为运行事实
- [ ] P1 · 根据至少一次原生请求级路由归属 + 实际业务结果，判定是否有可供评估的 GPT 专用候选；保持原有自动节点切换关闭，未知不推荐
- [ ] P1 · 在用户明确批准变更及具备回滚条件后，才讨论修改规则绑定/自动测试 URL 或启用 Shadowrocket 全局回退，避免误触生产节点
