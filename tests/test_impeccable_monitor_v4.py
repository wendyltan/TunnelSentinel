"""No fictional node controls, no persistent overview scrollbar."""
from pathlib import Path
import unittest
BASE=Path(__file__).resolve().parents[1]
S=(BASE/'menubar/TunnelSentinelMenu.swift').read_text()
INSTALL=(BASE/'install-menubar.sh').read_text()
class MonitorV4Tests(unittest.TestCase):
 def test_no_unverified_node_recommender(self):
  for banned in ('等待有效的候选数据','录入当前分组测速','找可试节点',
                 '手动测速建议','importNodeLatency','openNodeRecommendations',
                 'NodeAdvisorBridge','nodeAdviceForDisplay'):
   self.assertNotIn(banned,S)
  self.assertNotIn('TunnelSentinelNodeAdvisor.swift',INSTALL)
  self.assertNotIn('node_advisor.py',INSTALL)
 def test_unsupported_shadowrocket_rule_audit_is_not_an_entry(self):
  self.assertNotIn('核验 Shadowrocket 当前配置规则',S)
  self.assertNotIn('auditShadowrocketRules(_:)',S)
  self.assertIn('当前连接路径',S)
  self.assertIn('ChatGPT 实际节点',S)
 def test_flat_overview_four_values_in_one_panel(self):
  self.assertIn('let panel = AppearanceFillView(',S)
  self.assertIn('x: 0, y: 84, in: panel',S)
  self.assertIn('x: 282, y: 0, in: panel',S)
  self.assertIn('let card = NSView(frame:',S)
 def test_scroll_policy(self):
  self.assertIn('scroll.scrollerStyle = .overlay',S)
  self.assertIn('scroll.hasVerticalScroller = true',S)
  self.assertIn('scroll.scrollerStyle = .overlay',S)
if __name__=='__main__':
 unittest.main()
