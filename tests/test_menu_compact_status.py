"""Guard compact menu geometry and avoid promoting historical nodes to live."""
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parents[1]
menu = (root/'menubar/TunnelSentinelMenu.swift').read_text()
recovery = (root/'menubar/TunnelSentinelRecovery.swift').read_text()

class MenuCompactStatusTests(unittest.TestCase):
    def test_card_is_narrow_and_dividers_are_symmetric(self):
        self.assertIn('let w: CGFloat = 340', menu)
        self.assertIn('width: view.bounds.width - 40', menu)
        self.assertIn('width: w - 36, height: 106', menu)
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
        self.assertIn('let egressTitle = clashMode', card)
        self.assertIn(': observedEgress', card)
        self.assertIn('nativeGroupUIRecent ? snapshot.nativeGroupUINode',card)
        self.assertNotIn('snapshot.backendLastLoggedName',card)
        self.assertNotIn('snapshot.userLastVerifiedNode',card)

    def test_background_ax_read_is_read_only_and_fail_closed(self):
        self.assertIn('if let observed = IntegratedGroupController.currentNode()', recovery)
        self.assertIn('node:observed,armed:true',recovery)
        self.assertIn('reported("limited",reason:',recovery)
        self.assertIn('"limited":"监测中 · 切换受限"',recovery)
        self.assertIn('(0...105).contains(Int(Date().timeIntervalSince1970) - observed)',menu)

if __name__ == '__main__': unittest.main()
