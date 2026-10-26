"""Fail-closed contracts for real GPT-only Mihomo node switching."""
from pathlib import Path
import importlib.util
import json
import logging
import tempfile
import time
import unittest
from unittest import mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import clash_failover as c
import openai_link_guardian as g

class RealClashTests(unittest.TestCase):
 def test_write_gate_never_allows_shared_proxies(self):
  with self.assertRaises(ValueError):c.request('/proxies/Proxies','PUT',{'name':'x'})
  with self.assertRaises(ValueError):c.request('/proxies/AI','PUT',{'name':'x'})
  with self.assertRaises(ValueError):c.request('/configs','PUT',{'path':'x'})

 def test_only_actual_raw_nodes_allowed(self):
  self.assertTrue(c.allowed_node('🇯🇵 Japan 04',{'type':'AnyTLS'}))
  self.assertFalse(c.allowed_node('Proxies',{'type':'Selector'}))
  self.assertFalse(c.allowed_node('Traffic Reset：24 Days Left',{'type':'AnyTLS'}))
  self.assertFalse(c.allowed_node('31.86 G | 200.00 G',{'type':'AnyTLS'}))

 def test_rollback_after_unhealthy_switch(self):
  proxies={'Proxies':{'now':'shared'},'AI':{'now':'Proxies'},'current':{'type':'AnyTLS'},'target':{'type':'AnyTLS'}}
  group={'all':['current','target']}
  with mock.patch.object(c,'put_selection',side_effect=lambda node,grp: {'Proxies':{'now':'shared'},'AI':{'now':'Proxies'}}), \
       mock.patch.object(c,'verify_public_edge',return_value=False):
   with self.assertRaises(RuntimeError):c.perform_switch(proxies,group,'current','target')

 def test_real_trigger_requires_recent_three_codex_errors(self):
  with tempfile.TemporaryDirectory() as path:
   base=Path(path)
   (base/'config.json').write_text(json.dumps({'clash_auto_failover_enabled':True,'codex_stream_sqlite_monitor_enabled':True}))
   def status(errors=0):
    (base/'status.json').write_text(json.dumps({'proxy_client':'clash','route_management':'clash_observe_only','healthy':True,
     'codex_stream_diagnostics':{'state':'ok','scan_at':int(time.time()),'last_at':int(time.time()) if errors else 0,'recent_counts':{'broken_pipe':errors}}}))
   status(2)
   with mock.patch.object(c,'ROOT',base),mock.patch.object(c,'STATE',base/'state.json'),mock.patch.object(c,'validated_context') as vc:
    self.assertEqual(c.do_once()['state'],'armed');vc.assert_not_called()
   status(3)
   proxies={'Proxies':{'now':'shared'},'AI':{'now':'Proxies'},'old':{'type':'AnyTLS'},'new':{'type':'AnyTLS'}}
   with mock.patch.object(c,'ROOT',base),mock.patch.object(c,'STATE',base/'state.json'), \
        mock.patch.object(c,'validated_context',return_value=(proxies,{'all':['old','new']},'old')), \
        mock.patch.object(c,'select_candidate',return_value='new'), \
        mock.patch.object(c,'perform_switch',return_value={'ok':True}) as change:
    result=c.do_once();self.assertEqual(result['state'],'route_changed_business_pending');self.assertTrue(result['changed'])
    change.assert_called_once();self.assertEqual(json.loads((base/'state.json').read_text())['actions_today'],1)
    again=c.do_once();self.assertEqual(again['state'],'cooldown_or_daily_limit')
    self.assertEqual(change.call_count,1)

 def test_challenge_403_cannot_trigger_transport_failover(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp)
   (base/'config.json').write_text(json.dumps({'clash_auto_failover_enabled':True,'codex_stream_sqlite_monitor_enabled':True}))
   (base/'status.json').write_text(json.dumps({'proxy_client':'clash','route_management':'clash_observe_only',
     'healthy':False,'proxy_available':True,'recent_failure_score':4,
     'probes':[{'name':'edge','http_code':403}],
     'codex_stream_diagnostics':{'state':'ok','scan_at':int(time.time()),'last_at':0,'recent_counts':{}}}))
   with mock.patch.object(c,'ROOT',base),mock.patch.object(c,'validated_context') as vc:
    self.assertEqual(c.do_once()['state'],'armed');vc.assert_not_called()

 def test_guardian_disabled_by_default_for_other_macs(self):
  self.assertFalse(g.DEFAULTS.get('clash_auto_failover_enabled'))
  self.assertFalse(g.DEFAULTS.get('proxy_backend_auto_detect_enabled'))

if __name__=='__main__':unittest.main()
