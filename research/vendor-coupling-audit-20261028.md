# TunnelSentinel 代理软件耦合审计（2026-10-28 16:15–16:20 CST）

## 结论 / 检查边界

本轮只读检查 Mac mini `192.168.5.39` 仓库 `/Volumes/ExtSSD/Tools/TunnelSentinel`、Guardian 实际状态、menu/recovery/route Python & Swift 文件、代理入口助手与安装脚本；运行隔离模拟，**未修改生产程序、代理配置、进程或节点**。用户已对 1.6.6 原功能全部人工验收，本轮不应把代码审计当作新故障注入验收。

**事实**：16:18 CST 用户系统 HTTPS 代理真实变为 `127.0.0.1:7890`，监听进程来自非 Shadowrocket 的 `forest-co`，系统观察器返回 `listener_owner=other`；Guardian 状态 `proxy_client=system_proxy`、`route_management=system_proxy_observe_only`、`healthy=true`、`overall_status=attention`；`~/.codex/.env` 的 `HTTP_PROXY` 文件值亦已为 `http://127.0.0.1:7890`。注意：.env 变化不证明已运行的 ChatGPT/Codex 进程已重读新环境，整体 attention 不等于基础网络失败。原样保留。

## 已分离的通用层（有效）

- `scripts/system_proxy_observer.py`：macOS `scutil --proxy`，无供应商品牌依赖；对本机 TCP 监听进程只做有界只读观察，结果 `shadowrocket/other/unverified`，不能由端口推断机场节点。
- `openai_link_guardian.py::refresh_active_backend`：当前 macOS 明确的代理入口决定真正的监测路由，只有进程所有权证据才能判 Shadowrocket；其他代理用 `system_proxy`，PAC/无显式端口用未解析或 `system_route`，均 fail closed。
- Codex 本机日志断流/WS/HTTP 诊断、Computer Use 本机状态、公开 Cloudflare trace 出口、菜单 3 页与总览路径不需要特定代理 App；公共出口不是 ChatGPT 已登录请求节点。
- `scripts/codex_proxy_env.py` 与桌面脚本共享托管块，读取当前系统真实 HTTP 入口（不以 Shadowrocket 端口为准），独立备份及人工回退；目前仅允许 `127.0.0.1` HTTP/Mixed，SOCKS-only/PAC/TUN 不能自动同步，属于协议适配限制，不是特定品牌绑定。

## 残余耦合清单和优先级

1. **P0 / 功能不完整：Shadowrocket 掉线重连的所有权证据悖论**。`scripts/system_proxy_observer.py::inspect_listener_owner` 只在监听进程存在时确认所有者。`openai_link_guardian.py::refresh_active_backend` 在监听丢失时改认 `system_proxy`；随后 `cycle` 把非 Shadowrocket 代理当作 generic 并拒绝执行 `recover_missing_tunnel`。已用独立临时配置模拟：当前代理入口仍 `1082` 但监听进程不可确认，结果 `active_backend=system_proxy`、`WOULD_USE_SHADOWROCKET_RECOVERY=False`。**不会错重启其他软件，但现有“掉线重连”未完成真实掉线验收**。不要为了修复它放宽到“仅凭端口就重启”；未来如要保留专属自动恢复，需要经验证的进程身份、先前所有权、显式故障原因、手动暂停保护、独立故障模拟和回退。
2. **P1 / 不必要的后台私有数据依赖**：`openai_link_guardian.py::cycle` 只要认为当前代理是 Shadowrocket，就每周期执行 `current_shadowrocket_node()`，可访问应用受保护 Group Container，并最多经历两个只读子进程超时，即使 `native_fallback_enabled=false` 且自动控制全部 OFF。当前功能只需系统代理入口及公共出口，不应依赖全局节点。建议单独后续改为：默认不读取，只有用户授权/确有专属功能时才读；同步调整 UI `nodeUnverified` 相关旧提示和守护状态，避免未读被当成故障。
3. **P1 / 已废弃的组编辑器继续编译及定时检查**：`menubar/TunnelSentinelRecovery.swift` 与 `TunnelSentinelNativeRoute.swift` 仍硬编码四个过去的节点名和已删除的代理组；`IntegratedRecovery.start()` 每 45s 执行并把状态写入 `auto_route_ui_status.json`，虽当前 `enabled=false`、配置不满足不会编辑规则。这是旧功能负担，应待独立合约与迁移测试明确后移到未启用适配层或退役，不应复活旧组。
4. **P2 / Mihomo 只支持一个发行版的 socket 发现方式**：`scripts/clash_observer.py` 从 `~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml` 读取 `external-controller-unix`，并假设 `AI` 或 `TunnelSentinel-OpenAI` 分组。其他使用 Mihomo 内核的软件/自定义路径可能降级普通 `system_proxy`，但基础监测不受影响。今后应采用明确授权、只读 API 适配器发现/连接，不要扫描所有软件的私有目录或开启未授权 API。
5. **P2 / 残留 Shadowrocket 路径和恢复开关状态语义**：Guardian `DEFAULTS["proxy"]` 默认 `http://127.0.0.1:1082`，`shadowrocket_proxy` 初始化保存该历史值；在自动检测开启时仅用它作专属归属的双因子验证，不作为通用目标。菜单在所有者真实确认时显示专属隧道重连，属于合理可选依赖。但当用户已从 Shadowrocket 转到其他软件，`tunnel_recovery_enabled=true` 的配置可保留为潜在 dormant 值，不应误读成当前其他软件有自动重连能力。建议未来显式按 provider 保存可选恢复配置，不影响通用核心。
6. **P2 / 旧业务命名与未用辅助函数**：`openai_link_guardian.py` 的 `shadowrocket://select`、`current_shadowrocket_node`，`menubar/TunnelSentinelMenu.swift` 的旧 `openShadowrocket`、Clash 分组切换说明等在当前全部开关 OFF 时不应被用户当成已实现的通用控制。定向检查引用与已验证调用方后再清理死代码；保留有效的只读 Mihomo 请求级 API 适配器，不进行全项目盲删。

## 安全整改顺序（未实施）

- 先明确 P0 产品选择：禁用或下架未经过掉线故障验收的专属自动重连，或者设计带明确信号的安全恢复并离线故障测试；不能为修复功能把所有权证据放宽为端口名。
- P1 再剥离循环中的私有全局节点读取和常驻的旧分组 AX 轮询，优先删掉无用途代码/后台活动而非增加第二套功能。
- 最后扩展 Mihomo/HTTP/SOCKS/PAC/TUN 适配时依照真实接口分别测试；基础监测始终不变；没有请求级链路就不显示“实际节点”。
- 不重启 ChatGPT/Codex/当前代理软件，不切换任何节点；将来修改用户可见功能必须在聊天中提供可勾选实机验收清单。

## 本轮验证

- 真实切换：当前系统代理 `7890`，`listener_owner=other`，Guardian `system_proxy`，基础 `healthy=true`；Codex .env 文件同指 `7890`。
- 模拟故障：`1082` 但监听归属不可证实，当前逻辑不会调用 Shadowrocket 专属恢复，证明 P0 漏洞存在；仅隔离内存模拟，无实际断网。
- `AGENTS.md` 第 26–28 条仍有效：无旧组依赖、通用核心/可选适配器、每次交付聊天内人工验收。
