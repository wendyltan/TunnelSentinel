# TunnelSentinel

一个守护 Codex / ChatGPT 与 Shadowrocket 代理隧道的 macOS 后台服务。

当前版本：1.1.0

这是一个 macOS 后台守护程序，用于检测当前 Shadowrocket 节点到 ChatGPT 的连接质量，并在连续网络故障时切换到另一个已配置节点。

## 它解决什么

- 每 30 秒检查 `chatgpt.com` 的 TLS/Cloudflare 边缘连接。
- 只读取 ChatGPT 桌面 App 新产生的网络错误日志；不会读取聊天内容。
- 连续异常达到阈值后，通过 Shadowrocket 官方 URL Scheme 切换节点。
- 切换后立即复验；所有候选节点都失败时请求切回原节点。
- Shadowrocket 隧道异常退出时，通过官方 `shadowrocket://connect` URL Scheme 自动重新开启并复验。
- 若系统日志确认是用户手动关闭隧道，则进入“人工暂停”状态，不会擅自重新开启；用户再次手动开启后自动恢复守护。
- 本地代理端口未监听时优先恢复隧道，不再无意义地轮换所有节点。
- macOS 若未及时结束 URL Scheme 调用，3 秒后强制回收调用进程；是否切换成功仍以网络复验为准。
- 开机登录后由 `launchd` 自动运行，异常退出会自动拉起。

## 安全边界

- 不读取、复制或保存 ChatGPT Cookie、令牌与 Shadowrocket 节点密钥。
- 不读取 Shadowrocket 的私有 App Group 数据；节点切换只调用公开 URL Scheme。
- 不实际提交生图请求，因此不会消耗生图额度。
- 未登录后台请求可能被 Cloudflare Challenge 拦截，即使桌面 App 正常，因此守护程序不会主动访问内部后端或 WebSocket 入口。
- 自动切换以公开边缘探针失败，或桌面 App 新增的明确隧道、TLS、长连接、生图网络错误为依据。
- 单纯的 OpenAI 服务器 `5xx` 不应通过频繁换节点解决；核心边缘探测正常时不会立即切换。
- PubSub 正常关闭不计为故障，只有明确的连接失败或隧道/TLS错误参与判断。
- 人工关闭与异常退出依据 macOS Network Extension 的实际停止原因区分：`Stop command received` 保持关闭，`Plugin failed` 自动恢复。

## 默认策略

- 检查间隔：30 秒
- 150 秒窗口内累计 3 次失败才切换
- 切换后冷却 5 分钟
- 隧道异常退出后立即尝试恢复；失败后每 60 秒最多重试一次
- 人工关闭隧道后持续保持暂停，直到用户再次手动开启
- 候选顺序：日本2、新加坡1、新加坡2、德国、加拿大

可编辑安装目录中的 `config.json` 调整参数：

`~/Library/Application Support/OpenAILinkGuardian/config.json`

## 手工检查

```sh
python3 openai_link_guardian.py --config config.json --once --dry-run --verbose
```

查看运行状态：

```sh
cat "$HOME/Library/Application Support/OpenAILinkGuardian/status.json"
tail -f "$HOME/Library/Logs/OpenAILinkGuardian/guardian.log"
```

## 安装与移除

安装会复制运行文件到用户的 Application Support，并创建用户级 LaunchAgent：

```sh
./install.sh
```

停止开机运行但保留配置与日志：

```sh
./uninstall.sh
```

## 为什么不直接调用真实生图接口

真实生图需要当前 ChatGPT 登录态，而且每次生成都会消耗用量。守护程序只验证同一域名、TLS、Cloudflare 和后端入口，并以桌面 App 自己记录的生图网络错误作为补充信号。这样能够识别本次出现的代理/TUN/长连接故障，同时不会制造额外生图请求。
