# ChatGPT 节点健康资格与原生 fallback：可行性研究

> 2026-10-23，Mac mini / Shadowrocket macOS 2.2.92 / TunnelSentinel 1.5.0。
> **状态：研究完成，生产分流配置未修改。** 证据层次分别标注“实测”“手册”和“待验收”。

## 决策结论

**建议保留 Shadowrocket 原生 `fallback` 作为唯一自动换节点控制器。**
TunnelSentinel 负责被动 ChatGPT 业务诊断、出口变化观察和条件性告警，不并行轮换全局节点。
用户希望的“能用 ChatGPT 的节点自动选择”分为三个不同目标：

1. **逐节点网络可达（原生支持）**：`fallback` 对组内候选节点用一个 URL 周期测试；它选最近测试结果认为可用的节点。当前组按订阅+正则限定四个候选，间隔 60 秒、超时 5 秒，URL 为 `https://chatgpt.com/cdn-cgi/trace`。
2. **ChatGPT 页面/API/WebSocket 基础网络（可有限增强）**：TunnelSentinel 已观察到公共站点分流和应用日志，但没有对 *每个* 组内候选使用同一路由的能力；单次本机 `curl` 只测试当前被分组选中的路径。
3. **节点真正通过登录、历史会话、模型对话（尚无法自动证明）**：授权会话的客户端成功/失败事件不可由匿名 URL 推断。Cloudflare 403 和 429 也可能是反机器人/账号限流，不等于线路坏。

推荐先解决测试端点的误判风险，再判断是否需要自动调整候选范围。避免先引入第二套代理引擎或保存机场订阅凭据。

## 关键发现一：HTTP 请求方法会改变结果（本机实测）

2026-10-23 CST，同一 Mac mini、相同 `127.0.0.1:1082` Shadowrocket 本地代理，限定时间/独立连接：

| 公共地址 | HEAD | GET | 判断 |
|---|---|---|---|
| `https://chatgpt.com/cdn-cgi/trace` | **403** `cf-mitigated: challenge` | **200** | 不能只看 HEAD 的非 200 就把节点判定失效 |
| `https://chatgpt.com/favicon.ico` | 403 | 403 | 不适合作为这台 Mac 上的健康测试 |
| `https://chatgpt.com/robots.txt` | **200**（重复成功） | **200** | 候选 HEAD 兼容性较好，但 Cloudflare 静态资源可独立于业务使用 |
| `https://chatgpt.com/` | 403 | 403 | 反机器人挑战导致假阴性的可能性很高 |
| `https://openai.com/cdn-cgi/trace` | 403 | 200 | 与 ChatGPT trace 类似 |
| `https://www.gstatic.com/generate_204` | 204 | 204 | 仅证明通用出海可达，无法证明 ChatGPT 可达 |

Shadowrocket 手册明确说**其“CONNECT”连通性测试会对指定测试 URL 发 HTTP HEAD**。但**目前尚未通过 macOS 2.2.92 本机的抓包或组内测试页面验证自动 `fallback` 后台是否也发送 HEAD**：这是下一项关键核验，不能把文档描述直接当成后台实现证据。

**推荐受控 A/B（在副本里、停留观察旧组不受影响）**：用 Shadowrocket 自带“代理分组 → 测试”查看四个候选的实际通过率；先核实全局“延迟测试方法”以及分组后台是否沿用 HEAD；若确认 HEAD 问题，则在**可回退的测试配置副本**里比较 `robots.txt` 与 `cdn-cgi/trace`，观察实际选路和测试误差。默认不要立即改动运行中 URL，因为 `robots.txt` 的 200 仍不能说明登录或实时会话成功。

复现脚本：`scripts/research-chatgpt-probe-methods.sh`，完全只读、无 cookies、没有节点切换；只执行现有代理的 HEAD/GET 检查。

## 关键发现二：接口可复用边界

| 途径 | 能拿到的证据 | 不能做到的事 | 建议 |
|---|---|---|---|
| Shadowrocket 原生 `fallback`、`url-test` | 逐候选节点对**一个**测试 URL 的结果；原生后台自动选择 | 多个业务端点联合判定；登录后的完整 ChatGPT 状态 | **保留现有 fallback**；优先核实测试方法 |
| Shadowrocket 分组 GUI “测试” | 人工触发组内逐节点测速，保留候选名上下文 | 未找到稳定后台可读取的结果/逐组后端名称 API；UI 测试不等于自动健康机制 | 隔离验证 4 个候选，不当成周期性抓屏自动化 |
| `shadowrocket://select?s=...` | 文档可触发全局切换 | 之前本机返回成功但实际选中值不变，不能控制或证明命中 OpenAI 分组节点 | **不再用于自愈**；不要引入仅封装此 URL 的 Node 库 |
| 客户端业务日志 | HTTP 429、Cloudflare 挑战、线程目录同步、PubSub/WebSocket 关闭 | 如果没有节点名与时间精确绑定，不能对 **候选 A** 归因 | 延续被动诊断；未绑定前不能驱动逐节点黑名单 |
| Nexitally `aitest.html` | 在用户当前路线即时检查多个网站的公共 HTTP/出口信息 | 无服务商逐节点兼容性 API 或历史记录 | 已在 v1.5.0 复用检测思路；**保持只读** |
| 编辑纯文本的临时 HTTP 配置 API（社区文档） | 可读/写开放编辑窗口的配置缓冲区 | 不是逐节点健康状态 API；可能向 LAN 所有主机开放配置读写 | **禁止作为运行时控制面**；不要开启或调用 |
| 额外 Clash/Mihomo/sing-box 代理核心 | 在另一独立引擎中可建立 per-proxy API | 需导入/重用敏感订阅，第二套网络路由/占用端口与 Tailscale 冲突风险 | 仅在官方控制能力确实不足且用户另行批准架构时考虑 |

## 可落地的两层判定（后续实现条件）

1. **第一层：候选网络门槛**——Shadowrocket 组内原生检查。状态分“可达 / 超时 / 被挑战 / 未确认”，不将单次 403 直接判为永久封禁。
2. **第二层：当前会话质量**——TunnelSentinel 监测 *已选出口* 的会话列表同步、PubSub、HTTP 403 挑战、429 和 WebSocket 稳定性；独立显示“公共入口可达、业务需留意”，不把其他 AI 网站结果作为 ChatGPT 切换指令。
3. **融合规则（尚未自动启用）**——若能取得每个候选的可靠原生身份/测试数据，才建立逐节点短期隔离、连续异常阈值、至少 15 分钟冷却、最近成功节点回退；账号限流 429 只能提示，不可因其轮换出口。
4. **无法获取 per-node 控制接口时**——只展示建议与证据，让 Shadowrocket 原生 fallback 继续独立做选择。任何“看起来会切”但实际上没有原生执行证据的实现都不能标为通过。

## P0 下一实验与验收条件

- [ ] **HEAD vs GET 精确归因**：在原生“代理分组测试”中收集四个候选的结果，判明后台测试方法是否与全局 CONNECT 设置相同。由于 GUI 测试可能影响当前选路，使用非活动配置副本、明确回退，避免工作中断。
- [ ] **测试 URL 对照**：若后台确实使用 HEAD，比较 `trace` 与 `robots.txt` 的候选通过率，并确认后者没有造成明显“假可用”；需人类确认后才修改活动组。
- [ ] **业务覆盖**：检查官方 `wss://ws.chatgpt.com` 和 Codex `wss://chatgpt.com/` 长连接能稳定握手与持续通信，记录真实客户端会话同步情况；不要凭匿名握手承诺登录。
- [ ] **原生分组状态可读性**：寻找 Shadowrocket 公布/公开文档支持的无凭据、只读分组当前后端/最近测试结果接口。现在没有发现可靠接口，不能用历史 Seattle 05 替代实时数据。
- [ ] **真实故障观察**：维持用户决定“等自然故障再验收”，不要人为制造断网。下次自然故障记录故障时间、候选变化、公共出口和客户端恢复时间。

## 资料

- Shadowrocket 官方群组维护手册（社区存档）：https://github.com/LOWERTOP/Shadowrocket/wiki ，包括 CONNECT=HEAD、分组测试、单 URL、自动测试周期和 URL Schemes。
- Shadowrocket 代理分组参数：https://doc.repcz.link/shadowrocket/advance/
- OpenAI 网络/ WebSocket 建议：https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps
- Nexitally AI 自助测试：https://nxonearth.com/aitest.html
- macOS Shadowrocket 编辑器 API 相关实测（**不建议投入生产**）：https://github.com/daymade/claude-code-skills/blob/main/tunnel-doctor/references/proxy_conflict_reference.md
- 只封装 URL Schemes 的第三方 Node 包：https://www.npmjs.com/package/shadowrocket-node-switch （缺少节点清单/健康状态读取能力，无法解决本机旧 URL 已失效的问题）
