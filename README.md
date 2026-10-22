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

| 状态 | 含义 |
| :-- | :-- |
| **基础正常** | 公共代理入口可达，近期没有识别到业务错误；不保证每次聊天一定成功 |
| **需留意** | 代理可达，但客户端近期出现了验证、限流或连接等错误 |
| **连接异常** | 代理端口或公共入口探测失败，守护程序按既定规则恢复 |
| **节点检测中** | 节点已变化，新节点的健康状态尚未复核 |
| **节点未核实** | macOS 限制读取 Shadowrocket 节点，只展示明确标注的上次记录 |
| **待检测 / 暂停 / 离线** | 状态未更新、用户暂停或守护服务未运行 |

近期业务告警使用约 **3 分钟滚动窗口**。客户端一时重连不意味着代理应该切换；连续断线另有独立宽限机制。

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

## 从“检测到故障”到“确认恢复”

健康检查与恢复是两条不同的证据链：

1. **尽早发现：** 正常时约 30 秒检查一次；连续出现基础链路失败后，临时加密为约 10 秒一次，连续失败达到阈值才进入恢复。
2. **使用经过验证的候选：** 只考虑最近 72 小时内曾通过基础链路检查的节点。旧配置文件里找不到近期成功记录的节点，不再被盲目轮换；成功记录只代表候选资格，**不代表目前仍可用**。
3. **核验切换指令：** 发出节点选择指令后，必须确认 Shadowrocket 实际选中了目标节点；再向 ChatGPT 公共入口发起一次全新请求。两个条件全部通过才算恢复。
4. **失败有边界：** 如果 macOS 未执行节点切换，立即停止本轮连续尝试，避免把所有备用节点依次“假切换”。等待退避后再检查，并报告明确原因。
5. **保持人工介入入口：** 当软件无法核实节点或节点选择通道不可用时，菜单显示 **AI ! · 自动恢复受阻**，提供“打开 Shadowrocket 手动处理”。

**无法承诺的部分：** 如果 Shadowrocket 的自动切换入口失效、提供商全部节点不可用，或 OpenAI 服务端返回业务限流/验证错误，TunnelSentinel 不能保证直接修复。它会保留真实的异常状态，而不是显示一个误导性的“正常”。

**增强建议：** 为长期无人值守的使用场景，在 Shadowrocket 自身建立有可用节点、健康探测 URL 与超时设置的 [`fallback` / `url-test` 代理组](https://github.com/LOWERTOP/Shadowrocket/wiki/)，让实际流量走原生自动策略。TunnelSentinel 负责业务日志观察和外层告警。此处不会擅自改写你现有的规则与订阅，因为 Shadowrocket 的节点选择 URL 在某些 macOS 环境中可能没有实际效果。

## 守护流程

~~~text
Shadowrocket 本地代理
    ├─ 公共入口可达性 ──→ 链路健康 ──→ 失败计数 / 谨慎恢复 / 节点轮换
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
