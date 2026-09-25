# TunnelSentinel

TunnelSentinel 是一个面向 macOS 的轻量后台服务，用于守护 Codex / ChatGPT 使用的 Shadowrocket 代理链路。

当代理节点不可用时，它会自动切换并验证其他节点；当 Shadowrocket 隧道异常退出时，它会自动重新开启。若隧道由用户手动关闭，TunnelSentinel 会保持关闭状态，不会违背用户意图。

当前版本：1.1.0

## 功能

- 每 30 秒检查一次代理链路。
- 隧道异常退出时自动重新开启并验证。
- 用户手动关闭隧道时进入人工暂停，直到用户再次手动开启。
- 连续检测失败后自动切换候选节点。
- 新节点不可用时继续尝试其他节点，全部失败则回到原节点。
- 登录 macOS 后自动运行，守护进程异常退出后由系统重新拉起。
- 不读取聊天内容、Cookie、登录令牌或节点密钥。

## 恢复策略

TunnelSentinel 会先判断 Shadowrocket 的本地代理是否仍在运行：

1. 隧道异常退出：自动重新开启，恢复后立即验证链路。
2. 用户手动关闭：记录为人工暂停，不自动开启。
3. 隧道正常但链路连续失败：依次切换候选节点并复验。
4. 用户在人工暂停后重新开启隧道：自动恢复正常守护。

默认情况下，150 秒内累计 3 次失败才会切换节点；两次节点切换至少间隔 5 分钟。隧道恢复失败时，每 60 秒最多重试一次。

## 运行要求

- macOS
- 已安装并配置 Shadowrocket
- Python 3
- Shadowrocket 本地 HTTP 代理地址与 `config.json` 中的 `proxy` 一致

## 安装

在项目目录运行：

```sh
./install.sh
```

安装脚本会：

- 将运行文件复制到 `~/Library/Application Support/OpenAILinkGuardian`
- 创建用户级 LaunchAgent
- 启动后台服务
- 保留已有的运行配置

## 查看状态

```sh
cat "$HOME/Library/Application Support/OpenAILinkGuardian/status.json"
```

查看实时日志：

```sh
tail -f "$HOME/Library/Logs/OpenAILinkGuardian/guardian.log"
```

主要状态包括：

- `healthy`：当前链路是否可用
- `current_node`：守护记录的当前节点
- `tunnel_state`：`running`、`down` 或 `manual_pause`
- `manual_pause`：是否因用户手动关闭而暂停自动恢复

## 配置

首次安装会使用项目中的 `config.json`。安装后可修改：

```text
~/Library/Application Support/OpenAILinkGuardian/config.json
```

常用配置项：

- `proxy`：Shadowrocket 本地 HTTP 代理地址
- `nodes`：自动切换的候选节点
- `check_interval_seconds`：检查间隔
- `failures_before_switch`：触发节点切换所需的失败次数
- `tunnel_recovery_enabled`：是否自动恢复异常退出的隧道

修改运行配置后，需要重新加载后台服务才能生效。

## 手动检查

只检查一次且不执行恢复或节点切换：

```sh
python3 openai_link_guardian.py --config config.json --once --dry-run --verbose
```

## 移除后台服务

```sh
./uninstall.sh
```

该操作只移除 LaunchAgent，保留运行配置、状态和日志。


## macOS 状态栏菜单（新增）

可选安装原生菜单栏图标（不会修改已运行的 Python 守护进程、Shadowrocket 或节点配置）：

    ./install-menubar.sh

菜单显示 AI ✓（正常）、AI !（链路异常）、AI 待检（状态过期）、AI 离线（守护进程未运行）和 AI 暂停（用户暂停）。
菜单提供“暂停自动守护”“开启自动守护”“立即刷新状态”“查看守护日志”。“查看守护日志”直接打开可选择、可滚动的应用内日志窗口，支持“最近日志”和“切换与异常历史”两种筛选，以及刷新按钮，无须打开 Finder。暂停只停止网络守护程序，不关闭 Shadowrocket，也不影响 Remote Desktop Commander。暂停状态通过 macOS launchctl 持久化，重启后仍暂停；重新开启恢复登录自动运行。选择“退出状态栏图标”只关闭图标，守护程序继续运行。

菜单程序源代码位于 menubar/TunnelSentinelMenu.swift，登录自启文件为 ~/Library/LaunchAgents/com.wuwendi.tunnelsentinel-menu.plist，运行程序位于 ~/Library/Application Support/OpenAILinkGuardian/TunnelSentinelMenu。需要卸载状态栏图标时，可先运行 launchctl bootout gui/$(id -u)/com.wuwendi.tunnelsentinel-menu，再删除其 plist 与菜单二进制文件，不影响 Python 守护进程。

状态栏图标只报告 status.json 中的健康结果（且文件更新时间不超过 120 秒），它不是完整的 ChatGPT 登录状态、生图端到端成功检测。

### 自动切换的触发条件与核对

自动守护开启且 dry_run 为 false 时，在启动宽限期过后，最近 150 秒累计至少 3 次失败、且距离上次切换至少 300 秒时，会依次请求 Shadowrocket 切换候选节点，稍等并重新执行网络探测；检测恢复后记录 failover succeeded，全部候选失败则请求回到原节点。单次正常探测不会切换。

菜单“切换与异常历史”会从当前 guardian.log 及最多两份轮转日志中筛选触发、尝试、成功、失败及重连记录。failover succeeded 表示“已向 Shadowrocket 发送切换请求，且后续代理网络探测通过”，并不是独立读取 Shadowrocket UI 后确认其真实选中节点；“守护记录节点”同理是守护程序保存的节点名。重启守护程序后 last_switch_monotonic 会归零，因此核查历史切换请以日志为准。
