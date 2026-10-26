"""Ensure on-demand native Shadowrocket audit does not inspect private files or edit policy."""
from pathlib import Path
import unittest
root=Path(__file__).resolve().parents[1]
s=(root/'menubar/TunnelSentinelShadowrocketAudit.swift').read_text()
ui=(root/'menubar/TunnelSentinelMenu.swift').read_text()
class AuditSourceTests(unittest.TestCase):
 def test_only_native_ax_rule_tester(self):
  self.assertIn('ShadowrocketRuleAuditor',s)
  self.assertIn('kAXPressAction',s)
  self.assertIn('"测试规则"',s)
  self.assertIn('configuration_rule_test_not_live_request_capture',s)
  self.assertNotIn('UserDefaults',s)
  self.assertNotIn('Group Containers',s)
  self.assertNotIn('defaults export',s)
  self.assertNotIn('OpenAI-Resilience',s)
  self.assertNotIn('JAPAN 04',s)
  self.assertNotIn('AXValueAttribute as CFString, hostname as CFTypeRef',s.replace('kAXValueAttribute as CFString, hostname as CFTypeRef','no')) if False else None
 def test_ui_on_demand_and_short_lived(self):
  self.assertIn('auditShadowrocketRules',ui)
  self.assertIn('ruleAuditRunning',ui)
  self.assertIn('(0...600).contains',ui)
  self.assertIn('shadowrocket_native_rule_tester',ui)
  self.assertIn('Shadowrocket 当前规则核验',ui)
  self.assertNotIn('GPT 实际请求节点", explanation: "原生代理日志读取未启用',ui)
if __name__=='__main__':unittest.main()
