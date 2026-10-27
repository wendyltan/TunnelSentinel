# TunnelSentinel · 深色模式界面专项修复

日期：2026-10-27 北京时间。此版专门修复用户家中 Mac 夜间模式下的监控中心「大面积浅灰卡片、对比差、丑陋」问题。

## 原因
- macOS defaults read -g AppleInterfaceStyle 实机确认 Dark 模式，打开真实监控中心，截图见 ~/.cache/ts-dark-before-overview.png。大块亮灰控件背景叠在深色窗口上，浅色文本叠浅灰底。
- 原因是把 NSColor.controlColor.withAlphaComponent(0.54) 用作大面积自绘卡片背景，Dark Aqua 的 controlColor 可解析成明亮灰控件材料；总览和时间线由此产生了不统一且低可读性的灰块。

## 新视觉规则
- SentinelSurface 定义 hero/tile/event/row/menu 语义层，根据每个视图的 effectiveAppearance 在 draw 时分别选取真正适配的色值。
- Dark 使用低亮冷色面板：hero #212B37，tile #23272D，event #24282F，row #1E2126，menu #20252B；Light 使用 #F3F8FD 至 #FDFDFE 的浅色系。边界只用细且透明的线，不加厚重阴影。
- 保留 macOS 原生系统主次文字、SF Symbols 和绿色/蓝色/橙色等状态语义，采样时间改用更清晰的 secondaryLabelColor。
- 将时间线详情与概览导航改成蓝色无边框操作链接，避免看起来像禁用状态。
- 切换标签或再次从菜单打开监控窗口后，将新内容加载完再复位滚动位置，防止顶部健康摘要被上个标签的滚动偏移截掉。
- 菜单栏 AppKit-only；不修改 Guardian、代理节点、订阅、系统代理、自动故障转移或用户已开启的隧道掉线重连。

## 验收
- Swift 五个模块静态类型检查通过，签名 App 安装到 ~/Applications/TunnelSentinel.app，并通过 codesign --verify --strict。
- Python 回归 178/178 通过，新主题测试断言 Dark 背景都处于低亮范围，不再使用灰块原始 controlColor。
- 当前系统 Dark 模式实机截图：~/.cache/ts-dark-after-overview.png、~/.cache/ts-dark-after-timeline.png、~/.cache/ts-dark-after-diagnostics.png。实机确认灰块消失，文字/链接与主题协调。
- 只是实测 Dark；Light 模式由动态色值和代码回归校验，未擅自改变用户 macOS 全局系统主题进行截图。
- 安装脚本已备份旧 App：~/Library/Application Support/OpenAILinkGuardian/backups/branding-20261027-191612。
- 先前未提交的节点建议 P1 改动仍留在工作区；本项主题修复应单独 commit/tag。
