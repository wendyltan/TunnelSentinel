"""macOS actual-system-route proxy isolation and backend truthfulness tests."""
import json,logging,tempfile,unittest
from pathlib import Path
from unittest import mock
import openai_link_guardian as g
from scripts.system_proxy_observer import parse_scutil, inspect_listener_owner

HTTP="""HTTPEnable : 1
HTTPProxy : 127.0.0.1
HTTPPort : 7890
HTTPSEnable : 1
HTTPSProxy : 127.0.0.1
HTTPSPort : 7890
SOCKSEnable : 1
SOCKSProxy : 127.0.0.1
SOCKSPort : 7891
"""
class ProxyObserverTests(unittest.TestCase):
 def test_current_system_https_not_legacy_port(self):
  x=parse_scutil(HTTP)
  self.assertEqual(x['proxy_url'],'http://127.0.0.1:7890')
  self.assertEqual(x['endpoint'],'127.0.0.1:7890')
  self.assertEqual(x['state'],'explicit')
 def test_socks_only_and_dns_via_socks(self):
  x=parse_scutil('SOCKSEnable : 1\nSOCKSProxy : 127.0.0.1\nSOCKSPort : 7891')
  self.assertEqual(x['proxy_url'],'socks5h://127.0.0.1:7891')
 def test_pac_is_unknown_not_false_failure(self):
  self.assertEqual(parse_scutil(HTTP+'ProxyAutoConfigEnable : 1\n')['state'],'pac_unresolved')
 def test_direct_or_tun(self):
  self.assertEqual(parse_scutil('HTTPEnable : 0\nHTTPSEnable : 0\n')['state'],'direct_or_tun')
 def test_reject_invalid_injected_endpoint(self):
  self.assertEqual(parse_scutil('HTTPSEnable : 1\nHTTPSProxy : user:secret@localhost\nHTTPSPort : 7890')['state'],'invalid')
 def test_https_priority(self):
  x=parse_scutil(HTTP.replace('HTTPSPort : 7890','HTTPSPort : 7895'))
  self.assertEqual(x['proxy_url'],'http://127.0.0.1:7895')
 def svc(self,td):
  cfg=dict(g.DEFAULTS);cfg.update(proxy_backend_auto_detect_enabled=True,proxy='http://127.0.0.1:1082',
       tunnel_recovery_enabled=True,automatic_control_enabled=False)
  return g.Guardian(cfg,logging.getLogger('system-route-test'),Path(td)/'status.json')
 def test_unknown_third_party_never_uses_shadowrocket_preferences_or_reconnect(self):
  with tempfile.TemporaryDirectory() as td:
   svc=self.svc(td)
   r={'source':'macos_system_proxy','state':'explicit','proxy_url':'http://127.0.0.1:7890','endpoint':'127.0.0.1:7890'}
   with mock.patch.object(svc,'_inspect_system_route',return_value=r), \
        mock.patch.object(svc,'_inspect_mihomo',return_value={'active':False}),\
        mock.patch.object(g,'current_shadowrocket_node',side_effect=AssertionError('no shadowrocket pref')),\
        mock.patch.object(g,'latest_shadowrocket_stop_reason',side_effect=AssertionError('no old tunnel log')),\
        mock.patch.object(svc,'recover_missing_tunnel',side_effect=AssertionError('no shadowrocket connect')),\
        mock.patch.object(g,'proxy_endpoint_available',return_value=True),\
        mock.patch.object(svc,'probe_all',return_value=[g.ProbeResult('edge',True,200,False,.3)]),\
        mock.patch.object(svc,'maybe_begin_deep_probe'),\
        mock.patch.object(svc,'maybe_begin_ai_matrix'),\
        mock.patch.object(svc,'maybe_begin_codex_stream'),\
        mock.patch.object(svc.log_watcher,'read_new_failures',return_value=[]),        mock.patch.object(svc.log_watcher,'issue_summary',return_value=[]):
    self.assertTrue(svc.cycle())
   result=json.loads((Path(td)/'status.json').read_text())
   self.assertEqual(result['proxy_client'],'system_proxy')
   self.assertEqual(result['monitor_proxy_url'],'http://127.0.0.1:7890')
   self.assertEqual(result['route_management'],'system_proxy_observe_only')
   self.assertTrue(result['healthy'])
   self.assertFalse(result['current_node_verified'])
   self.assertEqual(result['current_node'],'')
   self.assertEqual(result['current_node_scope'],'system_proxy_endpoint_only')
 def test_switched_proxy_resets_stale_deep_and_shadows(self):
  with tempfile.TemporaryDirectory() as td:
   svc=self.svc(td)
   svc.deep_probe_result={'checked_at':1793100000,'targets':[{'name':'chatgpt_edge','state':'reachable'}]}
   svc.ai_matrix_checks=[{'name':'ChatGPT','status':'reachable'}]
   svc.current_node='stale Shadowrocket airport'
   svc.current_node_verified=True
   with mock.patch.object(svc,'_inspect_system_route',return_value={'source':'macos_system_proxy','state':'explicit','proxy_url':'http://127.0.0.1:7890','endpoint':'127.0.0.1:7890'}),\
        mock.patch.object(svc,'_inspect_mihomo',return_value={}):
    svc.refresh_active_backend()
   self.assertEqual(svc.active_backend,'system_proxy')
   self.assertEqual(svc.current_node,None)
   self.assertFalse(svc.current_node_verified)
   self.assertEqual(svc.deep_probe_result,{})
   self.assertEqual(svc.ai_matrix_checks,[])
 def test_pac_never_reports_offline_or_restarts_shadowrocket(self):
  with tempfile.TemporaryDirectory() as td:
   svc=self.svc(td)
   with mock.patch.object(svc,'_inspect_system_route',return_value={'source':'macos_system_proxy','state':'pac_unresolved','proxy_url':''}),\
        mock.patch.object(svc,'recover_missing_tunnel',side_effect=AssertionError('no recovery')):
    svc.cycle()
   s=json.loads((Path(td)/'status.json').read_text())
   self.assertEqual(s['overall_status'],'unknown')
   self.assertEqual(s['workflow_health']['network']['state'],'unknown')
   self.assertFalse(s['openai_egress_observed'])
 def test_unavailable_other_proxy_never_restarts_shadowrocket(self):
  with tempfile.TemporaryDirectory() as td:
   svc=self.svc(td)
   with mock.patch.object(svc,'_inspect_system_route',
              return_value={'source':'macos_system_proxy','state':'explicit',
                            'proxy_url':'http://127.0.0.1:7890','endpoint':'127.0.0.1:7890'}),\
        mock.patch.object(svc,'_inspect_mihomo',return_value={}),\
        mock.patch.object(g,'proxy_endpoint_available',return_value=False),\
        mock.patch.object(g,'latest_shadowrocket_stop_reason',side_effect=AssertionError('wrong owner')),\
        mock.patch.object(svc,'recover_missing_tunnel',side_effect=AssertionError('wrong owner')):
    self.assertFalse(svc.cycle())
   state=json.loads((Path(td)/'status.json').read_text())
   self.assertEqual(state['proxy_client'],'system_proxy')
   self.assertEqual(state['overall_status'],'offline')
   self.assertEqual(state['recovery_state'],'proxy_unavailable')
 def test_switch_to_direct_respects_missing_explicit_proxy(self):
  with tempfile.TemporaryDirectory() as td:
   svc=self.svc(td)
   with mock.patch.object(svc,'_inspect_system_route',return_value={'source':'macos_system_proxy','state':'direct_or_tun','proxy_url':''}),\
        mock.patch.object(svc,'probe_all',return_value=[g.ProbeResult('edge',True,200,False,.4)]),\
        mock.patch.object(svc,'maybe_begin_ai_matrix'),mock.patch.object(svc,'maybe_begin_deep_probe'),\
        mock.patch.object(svc,'maybe_begin_codex_stream'):
    svc.cycle()
   s=json.loads((Path(td)/'status.json').read_text())
   self.assertEqual(s['proxy_client'],'system_route')
   self.assertTrue(s['healthy'])
 def test_listener_provenance_is_real_process_not_historical_port(self):
  from types import SimpleNamespace
  def process(argv, **_):
   if argv[0].endswith("lsof"):
    return SimpleNamespace(returncode=0,stdout="p50557\n",stderr="")
   return SimpleNamespace(returncode=0,stdout="/Applications/Shadowrocket.app/Contents/PlugIns/MacPacketTunnel.appex/Contents/MacOS/MacPacketTunnel -AppleLanguages ...\n",stderr="")
  with mock.patch("scripts.system_proxy_observer.subprocess.run",side_effect=process):
   self.assertEqual(inspect_listener_owner("http://127.0.0.1:1082"),"shadowrocket")

 def test_other_process_reusing_shadowrocket_port_is_not_shadowrocket(self):
  from types import SimpleNamespace
  def process(argv, **_):
   if argv[0].endswith("lsof"):
    return SimpleNamespace(returncode=0,stdout="p22222\n",stderr="")
   return SimpleNamespace(returncode=0,stdout="/Applications/OtherProxy.app/Contents/MacOS/OtherProxy\n",stderr="")
  with mock.patch("scripts.system_proxy_observer.subprocess.run",side_effect=process):
   self.assertEqual(inspect_listener_owner("http://127.0.0.1:1082"),"other")

 def test_listener_unknown_fails_closed(self):
  with mock.patch("scripts.system_proxy_observer.subprocess.run",side_effect=OSError("no permission")):
   self.assertEqual(inspect_listener_owner("http://127.0.0.1:1082"),"unverified")
  with mock.patch("scripts.system_proxy_observer.subprocess.run",side_effect=AssertionError("no remote process scanning")):
   self.assertEqual(inspect_listener_owner("http://example.com:1082"),"unverified")

 def test_port_missing_distinct_from_permission_denial(self):
  from types import SimpleNamespace
  missing=SimpleNamespace(returncode=1,stdout="",stderr="")
  forbidden=SimpleNamespace(returncode=1,stdout="",stderr="Operation not permitted")
  with mock.patch("scripts.system_proxy_observer.subprocess.run",return_value=missing):
   self.assertEqual(inspect_listener_owner("http://127.0.0.1:1082"),"missing")
  with mock.patch("scripts.system_proxy_observer.subprocess.run",return_value=forbidden):
   self.assertEqual(inspect_listener_owner("http://127.0.0.1:1082"),"unverified")

if __name__=='__main__':unittest.main()
