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
