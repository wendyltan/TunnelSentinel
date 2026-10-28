"""Source-level guardrails for AppKit menu material and permissions scope."""
from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "menubar" / "TunnelSentinelMenu.swift").read_text()


class MenuSurfaceTests(unittest.TestCase):
    def test_custom_card_uses_native_menu_material(self):
        card = SOURCE.split("private func menuCard() -> NSView {", 1)[1].split(
            "private func menuItem(", 1)[0]
        self.assertIn("let v = NSView(frame:", card)
        self.assertNotIn("color: .windowBackgroundColor", card)
        self.assertIn("let nodeBox = AppearanceFillView(", card)

    def test_no_redundant_shadowrocket_private_preference_read(self):
        reader = SOURCE.split("private func refreshNode() {", 1)[1].split(
            "private var nodePending:", 1)[0]
        self.assertIn("liveNode = nil", reader)
        self.assertNotIn("process.executableURL", reader)
        self.assertNotIn("Group Containers", SOURCE)
        self.assertNotIn("defaults export", reader)


if __name__ == "__main__":
    unittest.main()
