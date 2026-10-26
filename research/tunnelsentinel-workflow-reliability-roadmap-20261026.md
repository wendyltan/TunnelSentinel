# TunnelSentinel：从“网络探测器”到“工作流可靠性观察器”

**评估日期：** 2026-10-26
**版本基线：** `272b24a`；Mac 系统 HTTP(S) 代理 Shadowrocket 127.0.0.1:1082；Guardian healthy=true，但 overall_status=attention；自动节点控制总开关 OFF，Clash/Shadowrocket 两种自动节点切换均 OFF；**隧道掉线重连由用户手动打开，当前 ON**。
**范围：** 只提出研发路线、验收与架构边界；不修改用户代理、订阅、节点、后台服务，未授权前不实施故障注入。

## 1. 已有产品价值
1. **单代理架构：** TunnelSentinel 不提供第二套 VPN/TUN；系统代理归属从 macOS 代理设置识别，避免与 Shadowrocket 冲突。可以在不改变既有工作流的情况下做检测。
2. **独立存活监测：** Guardian 在后台检查本地代理、ChatGPT 公共入口、出口地区，UI 失去焦点或关闭后仍可采样。
3. **真实客户端被动证据：** Codex `~/.codex/logs_2.sqlite` 中实际 GET /backend-api/codex/models、状态码和 WebSocket 建连事件；不会使用用户 Token 伪造业务请求。
4. **动态原生路由核验：** 通过 Shadowrocket 自带“测试规则”按需核对多域名当前命中策略与解析节点，既不硬编码机场节点名，也不访问 App Group 私有数据库。但不是请求级运行时归属证明。
5. **安全控制**：自动节点控制总闸门默认 OFF；读取与修改有独立能力边界；隧道掉线重连与节点切换分开。

## 2. 现存短板：按实际危险度排序
| 优先 | 已确认的实现现象 | 实际风险 | 处理策略 |
|---|---|---|---|
| P0 | `menubar/TunnelSentinelMenu.swift` 每 5 秒 `refreshStatus()` 仍在 AppKit 主线程同步 `launchctl print-disabled` 与 `launchctl print`，即便近期已将设置写入异步化 | GUI 卡顿、耗时子进程影响本应只读的菜单 | 改成后台低频状态采样/缓存；UI 只消费快照；绝不在主线程等待 shell |
| P0 | `Guardian.maybe_begin_deep_probe(healthy)` 仅在 `network_healthy=true` 才启动深度诊断 | 故障出现时可能恰好没有新鲜诊断，形成“健康时才详查” | 反转为异常时限频诊断增强：用分层、有限时、退避检测；仍不采集认证凭据 |
| P0 | `healthy=true` 但 `overall_status=attention`，客户端布局/浏览器错误易与真实代理故障混淆 | 告警疲劳、假故障切换诱因 | 独立三轴：网络、客户端业务、控制能力；三态：正常/异常/无证据；不活动不能显示为可用 |
| P0 | 当前 Shadowrocket 不开放受信任的持续请求级节点 API；规则测试为手动运行、10 分钟 TTL | 无法证明某条 GPT/Codex 请求使用哪个节点；锁屏控制不可靠 | 明确“配置规则匹配”≠“运行中请求节点”；保持自动节点切换禁用 |
| P1 | 当前 Codex 成功遥测主要是模型目录 HTTP 200、WS 建连等；不监测完整模型回复/浏览器执行 | 入口 200、WS 连上，不等于生图/上传/工具调用可用 | 从已存在的 Codex 日志归一化真实完成/断线/回退事件；需原始可用证据才能显示成功 |
| P1 | 事件、公共出口、设备路由、客户端异常没有统一“故障时间线” | 难定位 Clash/Shadowrocket、Cloudflare、上游与本地浏览器的原因 | 统一事件模型、关联窗口、保留来源、故障前后日志摘要，支持隐私友好导出 |
| P1 | 没有成熟的连续失败/恢复阈值、休眠后宽限、单事故合并提醒与历史指标视图 | 抖动误报、持续轮询冗余 | Gatus 式 hysteresis、睡眠/网络变化重新基线、按事故去重和静默 |
| P2 | 自动选节点对 Shadowrocket 没有经验证的无界面读写控制 | 自动化会比手动带来更高风险 | 独立研究后明确能力契约；不得擅自引入第二个内核或模拟“已恢复” |

## 3. 同类产品的正确借鉴
- **Uptime Kuma**（https://github.com/louislam/uptime-kuma）：HTTP/TCP/WebSocket/Ping/DNS/Push 多探针、历史曲线、事件通知与状态页。只学习事件数据模型和体验，不安装另一个后台监控系统。
- **Gatus**（https://gatus.io/docs/conditions 以及 https://gatus.io/docs/alerting-getting-started）：指标条件和连续失败/成功阈值、恢复通知。单次 TLS/HTTP 错误不应直接报成完整业务故障。
- **MetaCubeX Mihomo**（https://wiki.metacubex.one/en/config/proxy-groups/ 以及 https://wiki.metacubex.one/en/config/proxy-providers/）：`fallback/url-test`、`expected-status`、`lazy`、provider 动态候选与原生健康检查。即使迁移到 Clash，也应由**现有代理内核**执行切换，TunnelSentinel 做外部守护和证据验证。
- **Surge Mac**（https://manual.nssurge.com/tools/http-api.html）：有权限保护的本地 HTTP API，支持策略组读取、策略测试、活动请求、历史请求与配置敏感信息脱敏；如果未来确实需要可靠无人值守路由归属，比从 Shadowrocket 私有文件抓取更合理。但需整个代理客户端迁移、订阅配置兼容测试，且不保证 Computer Use 自然正常。
- **OpenAI 官方网络建议**（https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps）：ChatGPT `wss://ws.chatgpt.com`、Codex `wss://chatgpt.com` 的连接要求；仅说明目标主机与 WS 协议，匿名 GET/404 不能声称客户端业务已通过。
- **Google SRE**（https://sre.google/resources/practices-and-processes/incident-management-guide/）：按用户可观察症状告警，避免只监测原因且没有可操作建议。

## 4. 建议版本序列

### R1 / P0：监控器先做到“不影响工作”
- Guardian 后台拥有采集和状态合成；AppKit 菜单仅消费 1 份带版本、来源与采集时间的只读快照，防止主线程同步 shell。
- 生命周期：唤醒、Wi‑Fi/网络切换、代理软件切换后先重新建立基线，期间状态为“恢复识别中”，不立刻出故障通知；退出监控 App 不退出 Guardian。
- **故障时加测而不是故障时停测**；最多并行 2–3 个诊断动作，非故障低频；对失败的目的域名使用退避；不复制登录会话请求头、不抓包。
- 三个独立健康字段：`transport_health`、`codex_client_health`、`browser_control_health`，各自 `status=ok|degraded|failed|unknown`、`evidence_source`、`age_seconds`、`last_verified_success_at`。
- 交付验收：关机/唤醒或模拟守护进程超时不会卡死 UI；未知不能冒充成功；所有自动节点控制始终关闭；无人触碰系统代理。

### R2 / P1：真实业务症状与事故时间线
- 标准事件：`proxy_owner_changed`、`proxy_port_down`、`tls_handshake_failed`、`anonymous_ws_non101`、`codex_ws_connected`、`codex_response_failed`、`codex_response_completed`（仅有对应可信源时记录）、`browser_control_failed`、`openai_status_incident`。
- 每条事件标注**来源及证据等级**：PUBLIC_PROBE/CLIENT_LOG/NATIVE_RULE_MATCH/NATIVE_REQUEST_CONFIRMATION/MANUAL_E2E，禁止推导超过来源能力的结论。
- 故障切片：“开始时间→前后 3 分钟代理接管者/规则核验/ChatGPT 公共入口/Codex 错误/浏览器操作失败/恢复时间”；只保留必要元数据，默认保留 7 天、用户可清除和脱敏导出。
- 让用户自行触发一次普通非敏感网页的 Browser/Computer Use 烟测，程序只关联时间与日志，不在其工作浏览器中自行点击。
- 接入 OpenAI Status 的**服务类别**（ChatGPT、Codex、Work、文件上传），但官方显示整体正常并不代表个人业务可用。

### R3 / P1：长期可靠性仪表盘与有用的提示
- 近 24h/7d 实测可用时间、故障次数、连接恢复时长（MTTR）、最近一次真实 Codex WS 连接成功时间、真实客户端错误趋势、响应流 P95 延迟（仅有可比成功样本时）。
- 默认只提醒影响当前工作流的事情：建议候选初值“连续 3 次同层失败”触发，恢复需连续 2 次成功；事故 15 分钟内合并提示，睡眠宽限另定。全部作为验收后可调参数，不冒称测试已证实。
- 故障信息必须给出：**哪里有问题、证据、新鲜度、应当怎么办**，例如“代理端口正常，Codex WebSocket 近期重复断开；建议先保存当前工作，检查服务端状态，避免盲目切节点”。
- 不自动启动完整浏览器/图片生成/模型请求，不消耗额度。

### R4 / P2：恢复助手，而非自建代理
- **当前优先**：半自动、用户确认的恢复建议；以 Shadowrocket 原生规则测试结果为准，只读动态发现分组，不依赖订阅商节点名。仅提供“打开 Shadowrocket/查看规则核验”，不擅自切节点。
- 若将来代理客户端自然迁移为 **Surge 或 Clash Verge/Mihomo**，使用其公开本地只读 API 获得活动请求、策略组和可用候选；满足“可读当前→可控制单一 GPT 策略组→读回成功→真实客户端恢复”四项后，再申请用户显式启用自动切换。
- 每次候选切换记录原节点，冷却/隔离/回退；若缺失业务恢复证据，则状态是 `control_changed_unverified`，绝不能写“已恢复”。
- 不同时安装两套 TUN/系统代理内核，不自动迁移订阅密钥，不增加新的管理服务器。

## 5. 验收指标（**拟议目标，非当前实测**）
| 指标 | 拟议目标 |
|---|---|
| 菜单点击及开关响应 | UI 操作通常 <200ms；后台检查失败不阻塞主线程 |
| 状态准确性 | 没有新鲜证据时必须显示 Unknown/过期；公共 HTTP 200 不能推导 Codex/Computer Use 正常 |
| 误报约束 | 休眠唤醒、切换 Wi-Fi、代理暂时退出时产生一个清楚事件；不形成无穷重试风暴 |
| 数据成本 | 默认后台轻量探测，异常才有额外采样；日志滚动保留、支持脱敏导出 |
| 工作流验收 | 由用户在可控时段实际完成普通网页操作、Codex长流、ChatGPT上传等；失败时能在诊断时间线找到证据 |
| 代理安全 | 两个自动切换开关 OFF；隧道重连单独受控；没有未经允许的系统代理/节点写入 |

## 6. 当前明确不做
- 不通过 Shadowrocket 受保护的私有数据库逆向获取订阅凭据；不基于固定 AI 组名判定业务必然走哪个节点。
- 不复制 ChatGPT 会话 Cookie、Authorization 和其他身份头来伪造业务请求。
- 不在背景主动操控用户当前 ChatGPT/Computer Use 页面。
- 不主动切回 Clash、安装 Surge、重启代理或试验断网。
- 不用“服务端未记录错误”推导个人端到端工作流可用。

**下一步最小改动建议：** 先 R1（三轴状态、主线程性能、故障时补充探测），保持原四页监控中心；稳定后再做 R2 的事故时间线。自动节点控制等到需求/权限/API/真实业务验收具备后再重新审议。
