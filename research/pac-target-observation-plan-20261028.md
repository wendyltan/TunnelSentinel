# PAC 逐目标代理解析 · 设计门槛（2026-10-28）

本轮没有让监控进程在后台自动执行 PAC。macOS `scutil --proxy` 只提供 PAC 开关及脚本 URL，不能直接回答 `chatgpt.com` 的实际选择；不能根据历史 HTTP 端口猜测。当前 `system_proxy_observer.py` 已将其定义为 `pac_unresolved`，Guardian 对该状态显示「未知」而非断网。

官方 Apple CFNetwork API：`CFNetworkCopyProxiesForURL` 提供 URL 相关的代理列表；`CFNetworkExecuteProxyAutoConfigurationURL` 可能下载和执行 PAC 脚本。这属于实质网络与执行动作，必须由用户按需选择，不应在每 30 秒 Guardian 周期自动调用。

实施安全门槛：仅用户手动触发、只测白名单目的地 `https://chatgpt.com` / `https://api.openai.com`，不接触私人 URL、脚本正文、敏感 cookie；限制处理时长和输出，只返回代理类型与经脱敏的本机端口；按脚本 mtime/系统路由变化失效；无可信结果仍标为未知。默认不安装新的代理服务、不更改 PAC 配置、不让 PAC 测试成为自动切换触发器。

验证依赖：隔离无网络的静态 PAC fixture（DIRECT、PROXY、SOCKS、异常与超时），再在用户自然使用 PAC 的维护时段做明确授权的本机实测。平台参考：https://developer.apple.com/documentation/CFNetwork/CFNetworkExecuteProxyAutoConfigurationURL
