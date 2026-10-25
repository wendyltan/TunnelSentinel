"""Clash takeover and fail-closed Shadowrocket restoration contracts."""
import collections
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import openai_link_guardian as guardian

class GuardianClashTests(unittest.TestCase):
    def service(self, tmp):
        config=dict(guardian.DEFAULTS)
        config.update(proxy_backend_auto_detect_enabled=True,proxy='http://127.0.0.1:1082',native_fallback_enabled=True,native_fallback_group='OpenAI-Resilience')
        with mock.patch.object(guardian,'current_shadowrocket_node',return_value=None):
            return guardian.Guardian(config,logging.getLogger('clash-test'),Path(tmp)/'status.json')

    def test_detected_clash_never_performs_shadowrocket_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp);(Path(tmp)/'clash_observer.py').touch()
            payload={'source':'mihomo_unix_readonly','active':True,'proxy_url':'http://127.0.0.1:7897','api_healthy':True,'mode':'rule',
                     'observed_at':1710000000,'ai_group':'AI','ai_selection':'Proxies','selected_node':'nodeB',
                     'active_request_node':'nodeB','active_gpt_connections':3,'eligible_count':5}
            with mock.patch.object(guardian,'DEFAULT_HOME',Path(tmp)),mock.patch.object(guardian.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(payload))):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'clash')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:7897')
            with obj.codex_stream_lock:
                obj.codex_stream_result={'state':'ok','counts':{'broken_pipe':3},'recent_counts':{'broken_pipe':3},'last_at':1710000000}
            good=guardian.ProbeResult('edge',True,200,False,0.1,'','9.9.9.9','SIN','SG')
            obj.write_status([good],0,True)
            j=json.loads((Path(tmp)/'status.json').read_text())
            self.assertEqual(j['route_management'],'clash_observe_only')
            self.assertEqual(j['openai_group_backend_name'],'nodeB')
            self.assertTrue(j['openai_group_backend_verified'])
            self.assertEqual(j['proxy_client'],'clash')
            self.assertTrue(j['clash_failover_plan']['would_trigger'])
            self.assertFalse(j['clash_failover_plan']['will_change_routes'])

    def test_api_failure_does_not_fake_shadowrocket_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp);obj.active_backend='clash';obj.config['proxy']='http://127.0.0.1:7897'
            (Path(tmp)/'clash_observer.py').touch()
            payload={'source':'mihomo_unix_readonly','active':False,'reason':'TimeoutError'}
            with mock.patch.object(guardian,'DEFAULT_HOME',Path(tmp)),mock.patch.object(guardian.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(payload))):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'clash')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:7897')

    def test_only_verified_original_port_allows_switch_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp);obj.active_backend='clash';obj.config['proxy']='http://127.0.0.1:7897'
            (Path(tmp)/'clash_observer.py').touch()
            payload={'source':'mihomo_unix_readonly','active':False,'reason':'proxy_port_mismatch','system_proxy_port':1082}
            with mock.patch.object(guardian,'DEFAULT_HOME',Path(tmp)),mock.patch.object(guardian.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(payload))),mock.patch.object(guardian,'proxy_endpoint_available',return_value=True):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'shadowrocket')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:1082')

if __name__=='__main__':unittest.main()
