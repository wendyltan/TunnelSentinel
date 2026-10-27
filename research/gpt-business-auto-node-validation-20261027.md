# TunnelSentinel · 自动 GPT 业务节点验证研究

日期：2026-10-27。仅限架构研究与离线代码；不改变用户 Shadowrocket、订阅、节点、系统代理、自动切换设置、隧道重连开关。

## 用户真实需求
目标不是 ping 最快，而是某条线路能稳定完成 ChatGPT、Codex、Computer Use。手动粘贴延迟的前一版 P1 不满足需求，不应继续作为正式节点推荐方案。

## 对照项目与依据
- Mihomo 官方 API：https://wiki.metacubex.one/en/api/
  - GET /proxies 返回当前代理组及动态候选；GET /proxies/{name}/delay 可通过单个候选检查指定 OpenAI 公共入口，并可检查预期 HTTP 状态。
  - 注意 GET /group/{name}/delay 官方文档说会清除自动组固定选择，因此它不是完全无副作用的读操作。候选检查还需扩展到 WebSocket/TLS 与实际客户端证据。
- Surge Mac 官方 API：https://manual.nssurge.com/tools/http-api.html
  - 有策略组、单策略测试、活动请求、历史测试结果；url-test 等组发送 HEAD，不等于实际 GPT 成功。
  - https://manual.nssurge.com/policy-groups/url-test.html 说明网络变化时可以重新测试和用容差避免抖动。
- Shadowrocket wiki：https://github.com/LOWERTOP/Shadowrocket/wiki
  - 原生支持 url-test/fallback、指定健康检查 URL、interval/timeout/tolerance。代理组必须实际被 ChatGPT 分流规则引用；不能仅在配置里存在一个 AI 组。
  - 此前实机读取 ChatGPT/OpenAI 命中 PROXY 而非老历史 OpenAI-Resilience 组。当前没有找到可靠的后台只读 per-node 官方 API。
  - 社区资料 https://wiki.repcz.link/shadowrocket/faq/ 列出 shadowrocket://select?s=NAME 作为写选路 URL scheme；这会可能影响正在使用的节点，不是无扰动探测接口，macOS 行为尚未经测试。禁止悄悄轮流切换。
- OpenAI 官方网络建议：https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps
  - ChatGPT websocket 域名 ws.chatgpt.com、Codex websocket 域名 chatgpt.com，需要真正的 TCP443 Upgrade、长连接正常。
  - 匿名 HTTP 403/404 不能算业务 WebSocket 成功，也不能直接推断登录业务失败；HTTPS 200 也不能证明模型回答完成。
- Codex 代理参考实现：https://github.com/mehdic/codex-proxy
  - cheap health、模型列表和真正的 nonstreaming/streaming smoke test 分层。后者要认证和资源额度，TunnelSentinel 不会暗中重放登录凭据或创建后台模型回合。
- OpenAI 状态：https://status.openai.com
  - 分开 ChatGPT、Codex、Files、Computer Use 等服务端组件；多节点一起异常需先排除服务端故障。

## 四级证据
L0：确认 ChatGPT、Codex 域名目前实际命中哪个策略。策略组名绝不能由历史候选推断。
L1：通过指定候选的独立出口执行 OpenAI HTTPS 公共目标测试，必须有实际 per-node 绑定证明，结果十分钟过期。所有测试只能经过现有内核，无新 TUN。
L2：确认 chatgpt.com、ws.chatgpt.com 的 TLS 与 WebSocket 传输条件。匿名 Upgrade 或 root GET 不等于已登录对话成功。
L3：用户原本已发生的真实 Codex 任务完成、Responses/Remote Control 流稳定性，以及实际请求归属该节点的证据。只有同时满足才称「曾经业务验证」，从不声称未来保证不掉线。

推荐顺序：有真实成功且流稳定的候选 > OpenAI 专用传输条件较完整的候选 > 延迟。无候选归属、跨配置/订阅、过期、只有公共 GET200、仅测速时一律拒绝给出最佳节点。

## 此次已实现的离线门槛
- scripts/gpt_node_business_ranker.py：无网络读写、无用户凭据、无代理控制，仅评估来自未来受信任的 per-node adapter 的业务证据。
- tests/test_gpt_node_business_ranker.py：10 个边界测试，检查过期、不属于当前订阅、缺少真实节点归属、匿名 HTTP 不能代替真实业务、近期客户端错误会取消建议。
- 这不是 Shadowrocket 已支持自动候选检测的证明；当前设备上依旧无法自动获取当前订阅所有候选的独立 GPT 业务响应。

## 下一阶段
A. Shadowrocket 保留方案：通过原生 fallback 和专用 OpenAI 目标 URL，让 Shadowrocket 在内核内部自动做基础可用性恢复，Guardian 只读观察 Codex 真实成功／断流；任何规则变更先明确获批并保留回滚。由于没有 per-node read API，无法安全地对每个候选作严格的业务推荐。
B. 如果产品必须「无人值守、动态发现所有节点、不切换当前节点的逐候选 GPT 验证」，优先通过 Surge 或 Mihomo 官方单内核 API 实现独立节点测试，结合客户端真实日志；不能同时启动另一套代理核心，更不能再让 Shadowrocket 和 Clash 抢系统代理。
C. UI 的正式「推荐节点」需以业务证据置信度替代旧 35ms 延迟排序。在 L1/L2 接口不具备时显示「无法逐节点核验」，不能假装推荐已经上线。
D. 完整业务后验：只有真实完成回合且证据证明某请求走某节点才能标业务已验证；仍有未来失效风险。

## 未执行事项
本次没有安装/重启代理、没有后台扫用户所有节点、没有发登录请求、没有切换节点、没有打开任何新代理端口。旧手动录入 P1 目前仍留在已安装 App，标为待废弃实验，不代表这次研究已交付自动功能。
