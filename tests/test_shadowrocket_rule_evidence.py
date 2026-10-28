"""No unsupported Shadowrocket audit/obsolete tabs in user-facing monitor."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
MENU=(ROOT/"menubar/TunnelSentinelMenu.swift").read_text()
INSTALL=(ROOT/"install-menubar.sh").read_text()


class SimplifiedDashboardTests(unittest.TestCase):
    def test_three_tabs_only(self):
        self.assertIn('labels: ["总览", "记录", "设置"]', MENU)
        self.assertNotIn('labels: ["总览", "时间线", "诊断", "节点", "设置"]', MENU)
        self.assertNotIn('case 3:\n            dashboardHeading("当前节点与规则"', MENU)

    def test_obsolete_shadowrocket_rule_audit_removed(self):
        self.assertNotIn("ShadowrocketRuleAuditor", MENU)
        self.assertNotIn("auditShadowrocketRules", MENU)
        self.assertNotIn("recentNativeRuleAudit", MENU)
        self.assertNotIn("核验 Shadowrocket 当前配置规则", MENU)
        self.assertNotIn("TunnelSentinelShadowrocketAudit.swift", INSTALL)
        self.assertFalse((ROOT/"menubar/TunnelSentinelShadowrocketAudit.swift").exists())

    def test_unverified_node_is_not_promoted_to_success(self):
        self.assertIn('dashboardHeading("当前连接路径"', MENU)
        self.assertIn('dashboardCompactRow("macOS 代理入口"', MENU)
        self.assertIn('dashboardCompactRow("Codex / Work 入口"', MENU)
        self.assertIn('dashboardCompactRow("公开测试请求出口"', MENU)
        self.assertIn('dashboardCompactRow("ChatGPT 实际节点", value: "暂无法确认"', MENU)
        self.assertIn("同一个本机代理入口不代表最终公网出口相同", MENU)

    def test_record_retains_real_client_evidence(self):
        for term in ('dashboardHeading("连接故障与恢复"',
                     'dashboardHeading("实际客户端证据"',
                     'dashboardRow("Computer Use"',
                     'dashboardRow("Codex 响应流"',
                     'dashboardRow("Codex 实际 HTTP 请求"'):
            self.assertIn(term, MENU)
        self.assertNotIn('dashboardHeading("其他 AI 网站 · 公开探测"', MENU)

    def test_settings_keeps_proxy_sync_and_tunnel_recovery_but_no_disabled_node_toggle(self):
        self.assertIn("检测并同步当前代理", MENU)
        self.assertIn("撤销托管配置", MENU)
        self.assertIn('dashboardSwitch("隧道掉线重连"', MENU)
        self.assertNotIn('dashboardSwitch("自动节点控制"', MENU)
        self.assertNotIn('switchMenuRow("自动节点控制"', MENU)


if __name__ == "__main__":
    unittest.main()
