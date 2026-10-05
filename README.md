# TunnelSentinel

TunnelSentinel 是一个跑在 macOS 后台的小工具，专门看着 Shadowrocket 到 ChatGPT / Codex 的代理链路。

平时不用管它。网络只是短暂抖了一下，它会先等连接自己恢复；如果本地代理还在，但网络探测持续失败，它会换到下一个配置节点，并确认 Shadowrocket 真的选中了它、ChatGPT 的网络也已经恢复。Shadowrocket 隧道意外退出时，它会尝试重新开启。你自己手动关掉隧道时，它会尊重这个操作，不会马上替你打开。

当前版本：1.2.0

## 它现在能做什么

- 默认每 30 秒检查一次 Shadowrocket 本地代理和 ChatGPT 公共网络入口。
- 读取 Codex 本机日志，留意代理错误、TLS 错误和前台 PubSub 长连接断开。
- 忽略很快恢复的短暂重连。长连接断开超过 45 秒后，才开始计入失败；未恢复时每 30 秒最多再记一次。
- 在 150 秒内累计 3 次失败后尝试换节点，两次自动切换至少间隔 5 分钟。
- 切换后读取 Shadowrocket 当前节点并重新检查网络。两项都通过，才算切换成功。
- 所有备用节点都不可用时，请求回到切换前的节点。
- Shadowrocket 隧道异常退出时尝试重新开启，并检查本地代理和 ChatGPT 网络是否恢复。
- 分清 `用户手动关闭` 和 `隧道意外掉线`。手动关闭后暂停自动恢复，直到你再次开启隧道。
- 登录 macOS 后自动运行；守护进程意外退出时，由系统重新拉起。
- 状态栏菜单会显示链路状态、Shadowrocket 当前节点，并提供暂停、恢复、刷新显示和查看日志的入口。

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

菜单栏会显示：

- `AI ✓`：最近一次检查正常
- `AI !`：最近一次检查异常
- `AI 待检`：状态文件太久没有更新
- `AI 离线`：守护进程没有运行
- `AI 暂停`：你暂停了自动守护

菜单里的 `暂停自动守护` 只会停掉 TunnelSentinel，不会关闭 Shadowrocket。退出菜单栏图标也不会停止后台守护。

`AI ✓` 只说明最近一次公共入口探测通过。长连接日志刚出现异常时，菜单仍可能显示绿色，同时在后台累计失败分数。

## 平时怎么看它是否正常

大多数时候看菜单栏的 `AI ✓` 就够了。需要更多信息时，可以查看状态文件：

```sh
cat "$HOME/Library/Application Support/OpenAILinkGuardian/status.json"
```

几个常用字段：

- `healthy`：最近一次代理链路检查是否通过
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
