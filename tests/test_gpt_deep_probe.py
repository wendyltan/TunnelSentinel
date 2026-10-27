"""Public-layer checks must remain read-only and distinguish TLS from auth."""
import importlib.util
import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import json

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gpt_deep_probe',root/'scripts/gpt_deep_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
import openai_link_guardian as g

class DeepProbeTests(unittest.TestCase):
 def test_distinguish_tls_and_authenticated_business(self):
  self.assertEqual(probe.classify(0,200,'http200'),'reachable')
  self.assertEqual(probe.classify(0,403,'http200'),'challenge_or_rate_limit')
  self.assertEqual(probe.classify(0,404,'wss_handshake'),'tls_reachable_auth_or_path_unverified')
  self.assertEqual(probe.classify(0,421,'tls_only'),'tls_reachable_not_authenticated')
  self.assertEqual(probe.classify(35,0,'tls_only'),'transport_failed')
  self.assertEqual(probe.classify(56,403,'wss_handshake'),'http_response_with_transfer_error')
  self.assertEqual(probe.classify(0,101,'wss_handshake'),'upgrade_accepted')
  self.assertNotEqual(probe.classify(0,404,'wss_handshake'),'upgrade_accepted')

 def test_fixed_destination_allowlist_and_current_system_proxy_only(self):
  self.assertEqual(len(probe.TARGETS),6)
  self.assertIn(('codex_websocket','https://chatgpt.com/','wss_handshake'),probe.TARGETS)
  self.assertTrue(all(x[1].startswith('https://') for x in probe.TARGETS))
  for host in ('http://user:password@127.0.0.1:1234','ftp://127.0.0.1:8888','http://127.0.0.1:1234/path'):
   self.assertEqual(probe.scan(host)['state'],'invalid_system_proxy')
  with mock.patch.object(probe,'test_target',
                         side_effect=lambda item, proxy: {'name':item[0],'state':'reachable'}) as tested:
   for value in ('http://127.0.0.1:7890','socks5h://127.0.0.1:7891',''):
    x=probe.scan(value)
    self.assertEqual(x['state'],'completed')
   self.assertEqual(tested.call_count,18)

 def test_monitor_only_disable_all_route_controls(self):
  self.assertFalse(g.DEFAULTS['automatic_control_enabled'])
  self.assertFalse(g.DEFAULTS['tunnel_recovery_enabled'])
  with tempfile.TemporaryDirectory() as tmp:
   cfg={**g.DEFAULTS,'native_fallback_enabled':False,'clash_auto_failover_enabled':True}
   obj=g.Guardian(cfg,logging.getLogger('read-only-guard'),Path(tmp)/'status.json')
   obj.failure_times.extend([1.0,2.0,3.0])
   self.assertFalse(obj.should_switch())
   with mock.patch.object(obj,'known_good_candidates',side_effect=AssertionError('unexpected switch')):
    self.assertFalse(obj.attempt_failover())
   obj.active_backend='clash'
   with mock.patch.object(g.subprocess,'run',side_effect=AssertionError('unexpected helper')):
    obj.maybe_clash_failover()

 def test_layout_warnings_not_business_failures(self):
  watcher=g.LogWatcher(Path('/nonexistent'))
  for i in range(30):watcher.issue_events.append((__import__('time').time(),'layout'))
  self.assertEqual(watcher.issue_summary(),[])
  self.assertEqual(g.LogWatcher.classify_issue('IAB_LIFECYCLE iab backend info request failed'), 'browser_backend')
  self.assertIsNone(g.LogWatcher.classify_issue('Noise executor failed to connect to rendezvous noise_event'))

 def test_route_group_not_claimed_verified_from_config(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg={**g.DEFAULTS,'native_fallback_enabled':True,'native_fallback_group':'OpenAI-Resilience'}
   service=g.Guardian(cfg,logging.getLogger('group-evidence'),Path(tmp)/'status.json')
   service.write_status([g.ProbeResult('edge',True,200,False,0.5)],0,True)
   x=json.loads((Path(tmp)/'status.json').read_text())
   self.assertEqual(x['route_management'],'shadowrocket_policy_unverified')
   self.assertFalse(x['native_group_route_verified'])
   self.assertEqual(x['proxy_control_mode'],'read_only')
   self.assertFalse(x['tunnel_recovery_enabled'])

if __name__=='__main__':unittest.main()
