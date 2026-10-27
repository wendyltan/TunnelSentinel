"""Regression contract for macOS Dark Aqua readability."""
from pathlib import Path
import re
import unittest

SRC = (Path(__file__).resolve().parents[1] / "menubar" / "TunnelSentinelMenu.swift").read_text()

def brightness(rgb):
    return sum(rgb) / (255*3)

class AppearanceTests(unittest.TestCase):
    def test_surface_is_resolved_per_views_actual_appearance(self):
        self.assertIn('effectiveAppearance.bestMatch(from: [.darkAqua, .aqua])', SRC)
        self.assertIn('private enum SentinelSurface', SRC)
        for role in ('hero', 'tile', 'event', 'row', 'menu'):
            self.assertIn('case .'+role+': return rgb(', SRC)
        self.assertNotIn('controlColor.withAlphaComponent(0.54)', SRC)

    def test_dark_panels_are_dark_not_bright_grey(self):
        dark_branch=SRC.split('if isDark {',1)[1].split('switch self {',1)[1].split('        switch self {',1)[0]
        triples=re.findall(r'case \.\w+: return rgb\((\d+), (\d+), (\d+)\)',dark_branch)
        self.assertEqual(len(triples),5)
        for triplet in triples:
            rgb=tuple(map(int,triplet))
            self.assertLess(brightness(rgb),0.23)
            self.assertLess(max(rgb)-min(rgb),30)

    def test_no_large_cards_keep_system_control_color(self):
        self.assertIn('cornerRadius: 13, surface: .hero', SRC)
        self.assertIn('cornerRadius: 12, surface: .tile', SRC)
        self.assertIn('cornerRadius: 12, surface: .event', SRC)
        self.assertIn('cornerRadius: 9, surface: .row', SRC)
        self.assertIn('cornerRadius: 10, surface: .menu', SRC)

    def test_entry_links_and_scroll_position(self):
        self.assertIn('button.isBordered = false',SRC)
        self.assertIn('go.isBordered = false',SRC)
        self.assertIn('scroll.reflectScrolledClipView',SRC)

if __name__=="__main__":
    unittest.main()
