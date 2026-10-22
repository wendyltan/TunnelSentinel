# TunnelSentinel

TunnelSentinel 是一个跑在 macOS 后台的小工具，专门看着 Shadowrocket 到 ChatGPT / Codex 的代理链路。

平时不用管它。网络只是短暂抖了一下，它会先等连接自己恢复；如果本地代理还在，但网络探测持续失败，它会换到下一个配置节点，并确认 Shadowrocket 真的选中了它、ChatGPT 的网络也已经恢复。Shadowrocket 隧道意外退出时，它会尝试重新开启。你自己手动关掉隧道时，它会尊重这个操作，不会马上替你打开。

当前版本：1.3.0

## 它现在能做什么

- 默认每 30 秒检查 Shadowrocket 本地代理和 ChatGPT 公共网络入口；状态栏约每 2 秒尝试独立同步已选节点（需 macOS 允许读取 Shadowrocket 偏好设置）。
- 读取 Codex 桌面端本机日志，区分代理/TLS 故障和业务层 Cloudflare 验证、HTTP 429、连接中断、反复布局错误。业务告警不会直接触发自动换节点。
- 忽略很快恢复的短暂重连。长连接断开超过 45 秒后，才开始计入失败；未恢复时每 30 秒最多再记一次。
- 在 150 秒内累计 3 次失败后尝试换节点，两次自动切换至少间隔 5 分钟。
- 切换后读取 Shadowrocket 当前节点并重新检查网络。两项都通过，才算切换成功。
- 所有备用节点都不可用时，请求回到切换前的节点。
- Shadowrocket 隧道异常退出时尝试重新开启，并检查本地代理和 ChatGPT 网络是否恢复。
- 分清 `用户手动关闭` 和 `隧道意外掉线`。手动关闭后暂停自动恢复，直到你再次开启隧道。
- 登录 macOS 后自动运行；守护进程意外退出时，由系统重新拉起。
- 原生状态面板分别显示公共网络入口与客户端诊断；节点切换时提示待检，并主动请求后台立即复查。提供暂停、恢复、立即检测及事件记录入口。

## 它不会做什么

TunnelSentinel 不读取聊天内容、Cookie、登录令牌或节点密钥，也不会修改 Shadowrocket 的订阅。

它看到的是本机代理、ChatGPT 公共网络入口和 Codex 日志。它无法判断账号是否登录、OpenAI 服务端是否正常，也不能保证某次对话、远程任务或图片生成一定成功。

长连接监测来自 Codex 日志。TunnelSentinel 不会自己建立 WebSocket，也不能保证客户端永远不出现 `正在重新连接`。它做的是在持续断线时及时发现问题，并按既定规则恢复隧道或切换节点。

## 运行要求

- macOS
- 已安装并配置好 Shadowrocket
- Python 3
- Shadowrocket 本地 HTTP 代理地址与 `config.json` 中的 `proxy` 一致

默认代理地址是 `http://127.0.0.1:1082`。

## 安装

在项目目录运行：

```sh
./install.sh
```

安装脚本会把守护程序放到用户目录，创建登录自启服务并立即启动。已经存在的运行配置会保留。

如果还想要菜单栏图标，再运行：

```sh
./install-menubar.sh
```

菜单栏提供原生状态卡片：

- **基础正常**：公共代理入口可达，最近 3 分钟没有识别到相关客户端错误；**不能保证所有 ChatGPT 功能正常**。
- **需留意**：基础网络可达，但最近客户端日志有 Cloudflare 验证、429 限流、连接中断或密集的布局错误。
- **连接异常**：Shadowrocket 代理或公共入口检测失败；原有自动恢复规则继续执行。
- **节点检测中**：Shadowrocket 已切换节点，后端对新节点的检测尚未完成。
- **节点未核实**：系统限制了 Shadowrocket App Group 偏好读取，菜单只显示上次记录的节点；读取尝试设有超时，避免卡住后台。
- **已暂停、离线或待检测**：守护状态不可用或状态数据不够新。

菜单中的“立即检查链路”会向正在运行的守护进程发送轻量复查信号，不会重启 ChatGPT、Shadowrocket 或 Codex；它也允许再尝试一次受权限限制的节点读取。

菜单里的 `暂停自动守护` 只会停掉 TunnelSentinel，不会关闭 Shadowrocket。退出菜单栏图标也不会停止后台守护。

公共入口是否可达与业务日志告警是独立信息。未经认证的命令行请求可能正常触发 Cloudflare 验证，故不直接以 curl 首页的 HTTP 403 判定登录客户端故障。短暂断连也不会被当作永久故障；相关告警在约 3 分钟后自动过期。

## 平时怎么看它是否正常

日常可直接查看菜单栏的分层诊断。如果需要详细信息，可查看状态文件：

```sh
cat "$HOME/Library/Application Support/OpenAILinkGuardian/status.json"
```

几个常用字段：

- `healthy`：公共代理链路是否通过（兼容旧版本）
- `overall_status`：`reachable`、`attention` 或 `offline`，综合链路与最近客户端事件
- `business_status` / `business_issues`：基于客户端本机日志的分类摘要；没有近期错误不意味着所有业务接口均可用
- `pid`：守护进程 PID，菜单栏使用它发起不重启进程的即时复查
- `current_node`：守护程序记录的 Shadowrocket 节点；如果本轮读取失败，这里可能还是旧值
- `current_node_verified`：本轮是否成功读到并确认了这个节点；为 `false` 时不要只看上面的节点名
- `recent_failure_score`：最近 150 秒内还没有过期的失败分数
- `tunnel_state`：`running`、`down` 或 `manual_pause`
- `manual_pause`：是否因为你手动关闭隧道而暂停恢复

实时日志在这里：

```sh
tail -f "$HOME/Library/Logs/OpenAILinkGuardian/guardian.log"
```

菜单里的 `查看守护日志` 也能直接看最近日志和切换记录，不用去 Finder 里找文件。

## 自动恢复的规则

TunnelSentinel 默认使用下面这套节奏：

1. 本地代理端口消失时，先判断是用户手动关闭，还是 Shadowrocket 隧道异常退出。
2. 异常退出时请求重新开启隧道；失败后至少等 60 秒再试。
3. 代理还在，但 ChatGPT 网络或长连接持续异常时，把失败记入最近 150 秒的窗口。
4. 分数达到 3 且不在 5 分钟冷却期内时，从当前节点的下一个配置节点开始轮换尝试。
5. Shadowrocket 实际选中目标节点，而且网络检查通过后，才记录为切换成功。
6. 备用节点全部失败时，请求回到原节点。

服务刚启动后的前 45 秒不会自动切换，避免把启动过程中的短暂波动当成故障。

## 修改配置

运行中的配置位于：

```text
~/Library/Application Support/OpenAILinkGuardian/config.json
```

常用配置项：

- `proxy`：Shadowrocket 本地 HTTP 代理地址
- `nodes`：自动切换时使用的备用节点
- `check_interval_seconds`：检查间隔，默认 30 秒
- `failures_before_switch`：累计多少次失败后换节点，默认 3 次
- `failure_window_seconds`：失败分数保留多久，默认 150 秒
- `switch_cooldown_seconds`：两次自动切换之间至少等待多久，默认 300 秒
- `tunnel_recovery_enabled`：是否自动恢复异常退出的隧道

修改后需要重新加载守护服务才能生效。

## 只检查一次

下面的命令会检查一次，但不会恢复隧道或切换节点：

```sh
python3 openai_link_guardian.py --config config.json --once --dry-run --verbose
```

## 移除

移除后台守护：

```sh
./uninstall.sh
```

这个脚本会移除守护服务，但保留配置、状态和日志，也不会卸载菜单栏程序。

如果只想移除菜单栏图标：

```sh
launchctl bootout gui/$(id -u)/com.wuwendi.tunnelsentinel-menu
rm "$HOME/Library/LaunchAgents/com.wuwendi.tunnelsentinel-menu.plist"
rm "$HOME/Library/Application Support/OpenAILinkGuardian/TunnelSentinelMenu"
```

## 节点读取权限边界

在部分新版 macOS 环境中，非 Shadowrocket 自身的后台程序读取其 App Group 偏好文件可能被系统阻塞。TunnelSentinel 对这些读取设置了严格超时，菜单端在触发系统级阻塞后暂停自动重试，继续监测代理链路，并把节点明确标记为 **未核实**。因此，“约 2 秒同步”是权限允许时的刷新目标，不是所有环境都已通过的保证。无需为了绿色图标授权读取聊天记录、Cookie 或令牌。
