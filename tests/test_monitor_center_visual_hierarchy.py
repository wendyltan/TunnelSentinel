"""UI information architecture tests: no fake business success and no default log wall."""
from pathlib import Path
import unittest
s=(Path(__file__).resolve().parents[1]/'menubar'/'TunnelSentinelMenu.swift').read_text()
class VisualHierarchyTests(unittest.TestCase):
 def test_navigation_prioritizes_workflow_and_incidents(self):
  self.assertIn('NSSegmentedControl(labels: ["总览", "记录", "设置"]',s)
  self.assertIn('private func dashboardHealthTile(',s)
  self.assertIn('overviewHero(in: doc',s)
  self.assertIn('dashboardHealthTile("computer_use"',s)
  self.assertIn('查看记录',s)
 def test_incidents_are_grouped_by_day_and_expandable(self):
  self.assertIn('private func timelineEventCard(',s)
  self.assertIn('expandedTimelineEvents',s)
  self.assertIn('toggleTimelineDetails(_:)',s)
  self.assertIn('Calendar.current.isDateInToday',s)
  self.assertIn('codex_remote_session',s)
  self.assertIn('连接恢复不等于模型任务已完成',s)
 def test_backend_and_node_controls_stay_separated(self):
  self.assertNotIn('case 3:',s)
  self.assertNotIn('核验 Shadowrocket 当前配置规则',s)
  self.assertIn('dashboardHeading("实际客户端证据"',s)
  self.assertIn('Codex 实际 HTTP 请求',s)
  self.assertNotIn('dashboardProbe(_:)',s)
if __name__=='__main__':unittest.main()
