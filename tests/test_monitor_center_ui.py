"""Menu should be concise and use actual NSSwitch, not oversized alert walls."""
from pathlib import Path
import unittest
s=(Path(__file__).resolve().parents[1]/'menubar'/'TunnelSentinelMenu.swift').read_text()
class MonitorCenterTests(unittest.TestCase):
 def test_compact_short_menu(self):
  menu=s.split('let menu = NSMenu()',1)[1].split('statusItem.menu = menu',1)[0]
  self.assertIn('打开监控中心…',menu)
  self.assertIn('立即检测基础链路',menu)
  self.assertNotIn('switchMenuRow("自动节点控制"',menu)
  self.assertIn('switchMenuRow("隧道掉线重连"',menu)
  self.assertNotIn('GPT 分组节点 · 暂无近期读取',menu)
  self.assertNotIn('分组未核实（不可用）',menu)
  self.assertNotIn('查看 GPT 节点状态与事件',menu)
 def test_genuine_native_switch_and_guards(self):
  self.assertIn('let control = NSSwitch(',s)
  self.assertIn('control.action = #selector(switchChanged(_:))',s)
  self.assertIn('control.isEnabled = enabled',s)
  self.assertIn('snapshot.routeManagement == "clash_observe_only"',s)
  self.assertIn('snapshot.clashGroup == "TunnelSentinel-OpenAI"',s)
  self.assertIn('toggleTunnelRecovery()',s)
 def test_dashboard_is_distinct_and_confidence_labelled(self):
  self.assertIn('NSSegmentedControl(labels: ["总览", "记录", "设置"]',s)
  self.assertIn('DashboardFlippedView(',s)
  self.assertIn('ChatGPT 实际节点", value: "暂无法确认',s)
  self.assertIn('公开测试请求出口',s)
  self.assertNotIn('核验 Shadowrocket 当前配置规则',s)
  self.assertNotIn('dashboardProbe(_:)',s)
  self.assertNotIn('原生代理日志读取未启用；不会定时读取不存在的数据',s)
if __name__=='__main__':unittest.main()
