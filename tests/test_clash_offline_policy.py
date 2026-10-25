"""Synthetic Mihomo lab must stay outside production and leave other apps direct."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class OfflinePolicyTests(unittest.TestCase):
    def test_lab_policy_has_explicit_isolation(self):
        s=(ROOT/'research/clash-openai-offline-lab.yaml').read_text()
        self.assertIn('name: OpenAI-Recovery-Lab',s)
        self.assertIn('type: fallback',s)
        self.assertIn('enable: false',s)
        self.assertIn("external-controller: ''",s)
        self.assertIn('server: 127.0.0.1',s)
        self.assertEqual(s.count('server: 127.0.0.1'),2)
        for suffix in ('chatgpt.com','openai.com','oaistatsig.com','openaimerge.com'):
            self.assertIn(f'DOMAIN-SUFFIX,{suffix},OpenAI-Recovery-Lab',s)
        self.assertIn('MATCH,DIRECT',s)
        self.assertNotIn('PROXY-PROVIDER',s)
if __name__=='__main__':unittest.main()
