"""Guard compact menu geometry and avoid promoting historical nodes to live."""
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parents[1]
menu = (root/'menubar/TunnelSentinelMenu.swift').read_text()

class MenuCompactStatusTests(unittest.TestCase):
    def test_card_is_narrow_and_dividers_are_symmetric(self):
        self.assertIn('let w: CGFloat = 340', menu)
        self.assertIn('width: view.bounds.width - 40', menu)
        self.assertIn('width: w - 36, height: 104', menu)
        self.assertIn('width: w - 40, height: 18', menu)
        # The live AX menu and the custom card are each exactly 340pt wide.
        # Each right edge must land 20pt before the actual menu boundary.
        self.assertIn('frame: NSRect(x: w - 98, y: 287, width: 78', menu)
        self.assertIn('width: w - 184, height: 19', menu)
        self.assertIn('width: w - 159, height: 19', menu)
        self.assertNotIn('width: view.bounds.width - 21', menu)

    def test_status_bar_does_not_display_stale_or_global_node(self):
        section = menu.split('let compactEdge = ', 1)[1].split('statusItem.button?.contentTintColor',1)[0]
        self.assertIn('shortEgress', section)
        self.assertNotIn('backendCompactTitle', section)
        self.assertNotIn('compactGlobalNode', section)

    def test_historic_native_node_is_not_presented_as_current(self):
        card = menu.split('private func menuCard() -> NSView {',1)[1].split('private func menuItem(',1)[0]
        self.assertIn('let hasRequestRoute = snapshot.fresh && snapshot.backendVerified',card)
        self.assertIn('hasRequestRoute ? snapshot.actualBackendName : observedEgress',card)
        self.assertIn('只读监测 · 不自动换节点',card)
        self.assertNotIn('GPT 分组节点 · 暂无近期读取',card)
        self.assertNotIn('snapshot.nativeGroupUINode',card)
        self.assertNotIn('snapshot.backendLastLoggedName',card)
        self.assertNotIn('snapshot.userLastVerifiedNode',card)

    def test_deleted_group_controller_is_not_packaged_or_polled(self):
        install=(root/'install-menubar.sh').read_text()
        self.assertNotIn('TunnelSentinelRecovery.swift',install)
        self.assertNotIn('TunnelSentinelNativeRoute.swift',install)
        self.assertNotIn('IntegratedRecovery.shared.start()',menu)
        self.assertNotIn('IntegratedRecovery.shared.tick()',menu)
        self.assertFalse((root/'menubar/TunnelSentinelRecovery.swift').exists())
        self.assertFalse((root/'menubar/TunnelSentinelNativeRoute.swift').exists())

if __name__ == '__main__': unittest.main()
