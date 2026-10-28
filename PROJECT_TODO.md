# TunnelSentinel · 当前 TODO（2026-10-28）

> 实机安装基线 1.6.8（待本轮提交）。原 269 行历史任务已完整归档至 `research/todo-archive-20261028-pre-generalization.md`；这里仅列当前有效工作。过去已删除的 OpenAI-Resilience、独立 Route Controller、四固定节点控制器、旧规则核验、五标签 UI 均不作为现行待办。

## 按推荐顺序推进
- [x] **0 · 整理 TODO**：历史完整保存；现行任务与人工验收分开。
- [x] **1 · P2 通用 Mihomo 适配器**：从 Clash Verge Rev 的固定私有路径解耦；用户明确提供本地 Unix socket 后安全只读访问，严格核对 socket owner/权限与当前系统代理端口；不能识别时回退通用监控。
- [ ] **2 · P2 协议兼容**：SOCKS-only 当前入口与可验证健康探测；PAC 按目标域名解析而不是读取静态端口；TUN/直连继续通过实际出口检测。Codex .env 只允许确定且人工授权的可回退同步。
- [x] **3 · P1 真实业务关联**：Codex HTTP/WS 事件和 Computer Use 实际本机工具事件按时间、来源关联；绝不把进程在线/公开 HTTP 200 当成登录业务完成。
- [ ] **4 · 回归**：代理切换、相同端口复用、socket 权限异常、PAC、SOCKS、TUN、睡眠/唤醒后的陈旧数据失效。

## 人工验收（与开发独立）
- [ ] 1.6.8 菜单/总览/记录/设置；当前 Forest 7890 下无 Shadowrocket 专用开关；Codex .env 同步/撤销保留。
- [ ] Shadowrocket 实际 Plugin failed 的专属重连：已有隔离单测，真实异常尚未注入，需明确维护窗口。
- [ ] 用户正常执行一次 Computer Use，本机真实记录和时间线可核对；无云端回执时仍标未验证。
- [ ] SOCKS/PAC/TUN 使用场景的真实验收仅随用户自然切换，不为测试打断网络。

## 已完成基线
- [x] 1.6.7 P0/P1：可信短时所有权租约与保守异常重连；退出原生四节点编辑器及 45 秒轮询；停止私有节点偏好周期读取；227 项测试、实机安装。
- [x] 1.6.6 通用核心：系统代理当前入口、端口归属核验、真实证据才显示近期请求节点、Codex .env 安全管理。
- [x] Codex SQLite 错误和 Computer Use 本地执行状态只读观察，网络可达与业务完成分开；自动节点控制关闭。

相关文档：`HANDOFF.md`、`AGENTS.md`、`research/vendor-coupling-audit-20261028.md`。禁止擅改系统代理、路由、订阅、个人日志隐私权限，未经用户批准不进行真实断网故障注入。

## 2026-10-28 · 本轮开发进度（以此节优先于上方阶段标题）

- [x] **通用 Mihomo API 代码**：明确设置 `mihomo_socket_path`，只读核验本机 Unix socket 所有者、权限、API mixed-port；无固定 AI 分组仍可取 OpenAI 实时连接链。**其他客户端真实 socket 尚未验收，当前未启用新接入。**
- [x] **SOCKS/TUN 基础监控与协议警示**：SOCKS-only 走 socks5h 公开探测，TUN/直连保留无显式代理的实际出口检测；Codex 同步仅写经过确认的本机 HTTP/Mixed，不能推测 SOCKS 可被 Codex 自动使用。
- [x] **客户端时间证据**：Codex 流错误与本机 Computer Use 事件，双方数据有效、最近 30 分钟且相距不超过 120 秒时才提示「时间接近」，明确不证明因果/云端成功。
- [ ] **PAC 仍未实现目标 URL 动态解析**：Apple CFNetwork 支持目标 URL 的 PAC 处理，但自动执行可能加载 PAC 配置脚本；需设计独立的用户授权诊断，不将静态设置冒充真实分流。
- [ ] **人工验收新版本 UI**：新版安装后核对三标签、Forest 模式、Codex 代理只读说明、记录页仅在真实时间关联时出现诊断，切勿人为断开网络。
- [ ] **自然业务验收**：真实 Computer Use 最终完成回执仍无可靠云端来源；手动对照只可核实本机工具事件。
