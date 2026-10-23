from pathlib import Path
import unittest


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/shadowrocket-openai-fallback.fragment.conf"
OVERLAY = Path(__file__).resolve().parents[1] / "examples/shadowrocket-openai-domain-overlay.fragment.conf"
DOMAINS = ("chatgpt.com", "openai.com", "oaistatic.com", "oaiusercontent.com", "oaistatsig.com", "openaimerge.com")


class NativeFallbackDraftTests(unittest.TestCase):
    def setUp(self):
        self.text = EXAMPLE.read_text(encoding="utf-8")
        self.lines = [
            line.strip() for line in self.text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_fragment_has_both_sections_and_no_destructive_final_policy(self):
        self.assertEqual([row for row in self.lines if row.startswith("[")],
                         ["[Proxy Group]", "[Rule]"])
        self.assertNotIn("FINAL,", self.text)
        self.assertIn("DO NOT import this fragment", self.text)

    def test_group_is_a_fallback_with_at_least_two_placeholders(self):
        group = next(row for row in self.lines if row.startswith("OpenAI-Resilience = "))
        components = [p.strip() for p in group.partition("=")[2].split(",")]
        self.assertEqual(components[0], "fallback")
        self.assertIn("JP-Primary", components)
        self.assertIn("US-Backup-1", components)
        self.assertIn("interval=120", components)
        self.assertIn("timeout=5", components)
        self.assertIn("url=https://chatgpt.com/cdn-cgi/trace", components)

    def test_all_expected_openai_domains_route_to_same_group(self):
        rules = [row for row in self.lines if row.startswith("DOMAIN-SUFFIX,")]
        expected = {f"DOMAIN-SUFFIX,{domain},OpenAI-Resilience" for domain in DOMAINS}
        self.assertEqual(set(rules), expected)
        self.assertEqual(len(rules), len(expected))

    def test_domain_overlay_enables_only_openai_owned_suffixes(self):
        lines = [line.strip() for line in OVERLAY.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(lines, [
            "[Rule]",
            "DOMAIN-SUFFIX,oaistatsig.com,OpenAI-Resilience",
            "DOMAIN-SUFFIX,openaimerge.com,OpenAI-Resilience",
        ])

    def test_example_contains_no_subscription_endpoint_or_credentials(self):
        for sensitive in ("password=", "token=", "privateKey=", "user=",
                          "subscription_url", "ss://", "trojan://", "vless://"):
            self.assertNotIn(sensitive, self.text)


if __name__ == "__main__":
    unittest.main()
