<div align="center">

<img src="branding/ReadmeIcon.png" width="124" alt="TunnelSentinel icon" />

# TunnelSentinel

**让网络守护安静运行，让异常有迹可循。**

为 macOS 打造的轻量菜单栏守护工具。监控 Shadowrocket → ChatGPT / Codex 的连接状态，提供本地诊断与谨慎恢复。

<p>
<img alt="macOS" src="https://img.shields.io/badge/macOS-Native-121B38?style=flat-square&logo=apple&logoColor=white">
<img alt="Swift / AppKit" src="https://img.shields.io/badge/UI-Swift%20%2B%20AppKit-155F82?style=flat-square">
<img alt="Python 3" src="https://img.shields.io/badge/Guardian-Python%203-167C92?style=flat-square">
<img alt="Local-first" src="https://img.shields.io/badge/Privacy-Local--first-138B84?style=flat-square">
</p>

</div>

---

## 看得见问题，才谈得上恢复

**公共入口能打开，不等于 ChatGPT 一定好用。** TunnelSentinel 把代理基础连通性和桌面客户端业务异常分开检测：即使网络入口返回 HTTP 200，客户端出现 Cloudflare 验证、429 限流或连接关闭时，面板也能给出不同的提示。

<table>
  <tr>
    <td width="50%"><strong>◉ 链路守护</strong><br>巡检本地代理和公共入口。持续故障时按阈值与冷却时间谨慎恢复，尊重用户手动断开。</td>
    <td width="50%"><strong>⌁ 业务诊断</strong><br>读取本机相关错误日志，将验证、限流、连接中断与界面异常分类呈现。</td>
  </tr>
  <tr>
    <td><strong>◈ 原生状态面板</strong><br>菜单栏查看链路、节点和近期错误。单色 Template 标志随 macOS 外观自动适配。</td>
    <td><strong>◇ 克制的自动恢复</strong><br>不会因为一次 Cloudflare 403 或 HTTP 429 就盲目切换节点。</td>
  </tr>
</table>

## 菜单栏状态

菜单栏标志现在**直接显示与面板右上角徽标相同的状态文字**（例如“● 基础正常”“! 需留意”“! 需人工处理”）。文字颜色由 macOS 自动管理，以便在浅色、深色菜单栏和选中状态下保持可读性；点击仍可查看细分诊断信息。

**双节点视图：** 启用 Shadowrocket 原生 `fallback` 后，菜单栏同时展示健康状态、`出 US-SEA`（最近一次实际 OpenAI 请求的出口观测）、`全 Japan 04`（Shadowrocket 的全局手选节点）；点击后分别显示出口 IP/Cloudflare 机房编码以及完整的全局节点名。**出口 IP 和 Cloudflare `colo` 不能唯一确定机场订阅节点名称**；没有来自 Shadowrocket 的独立节点名证据时，界面会明确标注“非节点名”，绝不将历史上显示过的 `Seattle 05` 固定为当前后端。探测失败、状态过期时，出口显示“待确认”，不会沿用旧 IP；如果 macOS 限制读取 Shadowrocket 最新全局选择，则界面将最近确认过的名称标为“上次记录”，而不伪称实时。

| 状态 | 含义 |
| :-- | :-- |
| **基础正常** | 公共代理入口可达，近期没有识别到业务错误；不保证每次聊天一定成功 |
| **需留意** | 代理可达，但客户端近期出现了验证、限流或连接等错误 |
| **连接异常** | 代理端口或公共入口探测失败，守护程序按既定规则恢复 |
| **节点检测中** | 节点已变化，新节点的健康状态尚未复核 |
| **节点未核实** | macOS 限制读取 Shadowrocket 节点，只展示明确标注的上次记录 |
| **待检测 / 暂停 / 离线** | 状态未更新、用户暂停或守护服务未运行 |

近期业务告警使用约 **3 分钟滚动窗口**。客户端一时重连不意味着代理应该切换；连续断线另有独立宽限机制。客户端日志中明确出现的 **会话列表同步失败（例如 authenticated thread catalog 的 HTTP 403）** 也会单独提示，便于发现“公共入口正常、历史会话仍无法加载”的情况。此类 403、Cloudflare 验证和 429 都不会单独触发节点切换，避免反复更换出口加重验证问题。

> **关于 Cloudflare 验证：** 未携带登录态的命令行请求可能正常遇到 HTTP 403。TunnelSentinel 不读取 Cookie、令牌或聊天内容，因此使用公开入口验证基础连通性，并以真实桌面端日志辅助判断业务异常。

## 快速开始

**要求：** macOS、Shadowrocket、Python 3，以及可访问的本地 HTTP 代理（默认端口 1082）。

在已经获取的项目仓库根目录：

~~~sh
# 安装后台守护并设置登录自启
./install.sh

# 安装原生菜单栏程序、品牌图标和应用程序
./install-menubar.sh
~~~

应用安装在 **~/Applications/TunnelSentinel.app**；配置和运行状态仍保存在用户目录下的 **Library/Application Support/OpenAILinkGuardian**。升级菜单栏程序不会要求重启 ChatGPT、Codex 或 Shadowrocket。

## 设计与图标

<div align="center">
<img src="branding/ReadmeIcon.png" width="86" alt="Finder App icon" />
<br>
<sub>信号轨道 · 守望信标 · 深海蓝与薄荷青</sub>
</div>

菜单栏使用与品牌图标同源的**透明单色标志**，由系统按浅色、深色和选中状态自动着色；展开面板才使用绿色、橙色与红色表达健康状态，避免菜单栏文字对比度不足。

| 资源 | 用途 |
| :-- | :-- |
| <code>branding/AppIcon.icns</code> | 原生 App 在 Finder 中显示的图标 |
| <code>branding/MenuBarTemplate.png</code> | 状态栏自适应单色标志 |
| <code>branding/GenerateBranding.swift</code> | 可重复构建的矢量几何源码 |
| <code>branding/ReadmeIcon.png</code> | README 品牌预览 |

在 Mac 上运行 <code>./branding/build-assets.sh</code> 可重新生成所有资源。

## 从异常检测到恢复

TunnelSentinel 把**代理基础链路**、**ChatGPT 客户端错误**和**节点切换权**分开处理。

- 基础网络：正常情况下约每 30 秒检查一次，出现连续失败后约每 10 秒检查一次。
- 业务层：观察 Cloudflare 验证、HTTP 429、长连接中断等真实客户端错误；这些事件不会单独触发节点切换。
- **原生故障转移模式**：若 Shadowrocket 的 `fallback` 分组已经在当前规则中正确启用，由 Shadowrocket 自身决定 OpenAI 出口节点，TunnelSentinel 不再发送外部 `shadowrocket://select` 指令，避免双重控制。
- 传统模式：仍保留有界恢复与候选节点检查，但 macOS 上外部选择指令的成功回执不等于真正切换，不能承诺其一定可用。
- 全局节点名称与 OpenAI 规则组所选择的实际出口**可能不同**，菜单会明确区分两者。

> 公共探测 HTTP 200 和分流规则命中均不能替代断网条件下真实切换测试，也不能保证账号限流、Cloudflare 验证或 ChatGPT WebSocket 会自动恢复。

## 守护流程

~~~text
Shadowrocket 本地代理
    ├─ 公共入口可达性 ──→ 链路健康 ──→ 故障告警 / 复核
    ├─ 原生 fallback 模式 ──→ Shadowrocket 自主选路（不做外部强制换节点）
    └─ ChatGPT / Codex 桌面日志 ──→ 近期业务告警 ──→ 菜单栏诊断
                                             （不触发盲目换节点）
~~~

| 默认设置 | 数值 |
| :-- | --: |
| 基础网络巡检 | 正常每 30 秒；故障期间约每 10 秒 |
| 长连接断开宽限 | 45 秒 |
| 故障累计窗口 | 150 秒 |
| 切换阈值 | 窗口内 3 次失败（业务限流不累计） |
| 基础切换冷却 | 至少 5 分钟 |
| 失效控制通道的重试退避 | 15 分钟 |
| 候选节点成功记录窗口 | 72 小时 |
| 菜单健康状态读取 | 每 5 秒 |
| 节点信息尝试更新 | 约每 2 秒，受系统权限影响 |

**节点读取权限边界：** 部分 macOS 版本会限制第三方进程访问 Shadowrocket 的 App Group 偏好设置。工具会限制读取耗时，并在系统阻塞时停止自动重试；此时节点显示为“未核实”，但基础链路巡检仍继续进行。这里的 2 秒是权限允许时的目标，不是所有设备上都已实现的保证。

## Shadowrocket 原生故障转移（分阶段启用）

为提升无人值守的故障恢复能力，更合适的方案是让 Shadowrocket 自身的 `fallback` 代理组决定每条请求使用哪个节点，而 TunnelSentinel 独立观察链路与 ChatGPT 客户端诊断。这样可以避免额外的节点选择 URL 在 macOS 上失效导致连续盲试。

本仓库提供不包含订阅密钥的 [fallback 配置片段](examples/shadowrocket-openai-fallback.fragment.conf) 和 [安全启用与回退步骤](research/shadowrocket-native-failover.md)。安装程序**不会直接修改 Shadowrocket 配置**；分组必须通过 Shadowrocket 自身的配置机制创建，确保规则确实命中再启用。

2026 年 10 月的本地试点已验证：在保留原配置的前提下创建了 `OpenAI-Resilience` 组，启用测试配置后 `chatgpt.com`、`ws.chatgpt.com`、`api.openai.com` 都命中该分组，公共入口测试返回 HTTP 200。**强制使首选节点失效后的自动改选尚未验收**，不可把此次试点当作零中断保证。

## 配置与事件记录

运行配置位置：<code>~/Library/Application Support/OpenAILinkGuardian/config.json</code>

~~~json
{
  "proxy": "http://127.0.0.1:1082",
  "check_interval_seconds": 30,
  "failure_window_seconds": 150,
  "failures_before_switch": 3,
  "switch_cooldown_seconds": 300
}
~~~

以上只是部分选项；请在本机维护具体节点及后备顺序。自动恢复会跳过最近没有成功记录的旧名称，配置的优先级不会跳过实际健康验证。修改配置后需重新加载后台守护。

~~~sh
cat "$HOME/Library/Application Support/OpenAILinkGuardian/status.json"
tail -f "$HOME/Library/Logs/OpenAILinkGuardian/guardian.log"
~~~

菜单中的 **「立即检查链路」** 会请求正在运行的后台进行新一轮检测，不会重启其他应用。**「查看事件日志」** 则展示近期检测、失败与切换记录。

<details>
<summary><strong>开发与测试</strong></summary>

<br>

~~~sh
python3 -m unittest discover -s tests -v

swiftc -parse-as-library -O -framework AppKit \
  menubar/TunnelSentinelMenu.swift -o /tmp/TunnelSentinelMenu-preview

./branding/build-assets.sh
~~~

自动化测试与 Swift 编译只能验证代码行为；真实菜单布局、Finder 图标和不同 macOS 权限环境中的节点同步仍需要实机验收。

</details>

<details>
<summary><strong>停止、卸载与隐私</strong></summary>

<br>

- 在菜单中暂停自动守护，不会同时关闭 Shadowrocket。
- <code>./uninstall.sh</code> 移除守护服务，保留用户配置与日志。
- 如需单独停用菜单栏，可通过 <code>launchctl bootout gui/$(id -u)/com.wuwendi.tunnelsentinel-menu</code> 停止，然后按需手动移除 <code>~/Applications/TunnelSentinel.app</code>。
- 不读取聊天正文、Cookie、登录令牌或 Shadowrocket 订阅密钥；不自动修改订阅。

</details>

---

<div align="center">

**TunnelSentinel · Quietly watching the connection.**

<sub>本地优先 · 适度恢复 · 不以漂亮的「正常」掩盖真实故障</sub>

</div>
