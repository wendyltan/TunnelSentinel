"""Diagnostic probes must not pretend to be authenticated B-side requests."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('probe_method',ROOT/'scripts/gpt_deep_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
menu=(ROOT/'menubar/TunnelSentinelMenu.swift').read_text()

class HonestMethodContract(unittest.TestCase):
 def test_actual_official_ws_hosts_but_not_internal_urls(self):
  targets={k:(url,kind) for k,url,kind in probe.TARGETS}
  self.assertEqual(targets['chatgpt_websocket'],('https://ws.chatgpt.com/','wss_handshake'))
  self.assertEqual(targets['codex_websocket'],('https://chatgpt.com/','wss_handshake'))
  self.assertEqual(targets['chatgpt_edge'],('https://chatgpt.com/cdn-cgi/trace','http200'))
  self.assertEqual(targets['openai_api_tls'],('https://api.openai.com/','tls_only'))
  self.assertEqual(targets['openai_auth_tls'],('https://auth.openai.com/','tls_only'))
 def test_404_is_not_ws_upgraded(self):
  def fake_target(item,proxy):
   return {'name':item[0],'state':probe.classify(0,404,item[2]),'http_code':404}
  with mock.patch.object(probe,'test_target',side_effect=fake_target):
   result=probe.scan('http://127.0.0.1:1082')
  self.assertFalse(result['websocket_transport_ok'])
  self.assertTrue(result['websocket_host_http_reachable'])
  self.assertFalse(result['codex_websocket_upgrade_verified'])
  self.assertIn('anonymous_',result['limitations'])
 def test_main_thread_does_not_wait_for_guardian_restart(self):
  setting=menu.split('private func updateMonitorConfig(',1)[1].split('@objc private func toggleAutomaticControl',1)[0]
  self.assertIn('DispatchQueue.global(qos: .utility).async',setting)
  self.assertIn('let limit = Date().addingTimeInterval(8)',setting)
  self.assertIn('process.arguments = ["kickstart", "-k", service]',setting)
  self.assertNotIn('runLaunchctl(',setting)
 def test_ui_discloses_synthetic_requests(self):
  # Synthetic probes still exist in the passive backend but are no longer
  # presented as actionable business success or a dedicated dashboard.
  self.assertNotIn('模拟 GET / + Upgrade（无登录）',menu)
  self.assertNotIn('Codex WebSocket 域名',menu)
  self.assertIn('Codex 实际 HTTP 请求',menu)
  self.assertIn('公开测试请求出口',menu)
  self.assertIn('ChatGPT 实际节点',menu)

if __name__=='__main__': unittest.main()
