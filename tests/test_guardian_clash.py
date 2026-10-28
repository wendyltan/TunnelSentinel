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

    def test_auto_backend_init_never_reads_protected_shadowrocket_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=dict(guardian.DEFAULTS)
            cfg.update(proxy_backend_auto_detect_enabled=True)
            with mock.patch.object(guardian,'current_shadowrocket_node',side_effect=AssertionError('private preference read')):
                obj=guardian.Guardian(cfg,logging.getLogger('privacy-test'),Path(tmp)/'status.json')
            self.assertFalse(obj.current_node_verified)

    def test_detected_clash_never_performs_shadowrocket_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp)
            payload={'source':'mihomo_unix_readonly','active':True,
                     'proxy_url':'http://127.0.0.1:7897','api_healthy':True,
                     'ai_group':'AI','ai_selection':'Proxies','selected_node':'nodeB',
                     'active_request_node':'nodeB','active_gpt_connections':3,'eligible_count':5}
            with mock.patch.object(obj,'_inspect_system_route',
                        return_value={'source':'macos_system_proxy','state':'explicit',
                                      'proxy_url':'http://127.0.0.1:7897','endpoint':'127.0.0.1:7897'}), \
                 mock.patch.object(obj,'_inspect_mihomo',return_value=payload):
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

    def test_api_failure_keeps_actual_system_route_without_faking_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp);obj.active_backend='clash';obj.config['proxy']='http://127.0.0.1:7897'
            with mock.patch.object(obj,'_inspect_system_route',
                        return_value={'source':'macos_system_proxy','state':'explicit',
                                      'proxy_url':'http://127.0.0.1:7897','endpoint':'127.0.0.1:7897'}), \
                 mock.patch.object(obj,'_inspect_mihomo',return_value={'active':False,'reason':'TimeoutError'}):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'system_proxy')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:7897')

    def test_original_port_returns_shadowrocket_only_when_selected_in_system_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp);obj.active_backend='clash';obj.config['proxy']='http://127.0.0.1:7897'
            with mock.patch.object(obj,'_inspect_system_route',
                        return_value={'source':'macos_system_proxy','state':'explicit',
                                      'proxy_url':'http://127.0.0.1:1082','endpoint':'127.0.0.1:1082',
                                      'listener_owner':'shadowrocket'}), \
                 mock.patch.object(obj,'_inspect_mihomo',side_effect=AssertionError('no need')):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'shadowrocket')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:1082')

    def test_other_proxy_reusing_old_shadowrocket_port_is_generic_and_never_restarts_shadowrocket(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp)
            with mock.patch.object(obj,'_inspect_system_route',
                       return_value={'source':'macos_system_proxy','state':'explicit',
                                     'proxy_url':'http://127.0.0.1:1082','endpoint':'127.0.0.1:1082',
                                     'listener_owner':'other'}), \
                 mock.patch.object(obj,'_inspect_mihomo',return_value={}):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'system_proxy')
            self.assertEqual(obj.config['proxy'],'http://127.0.0.1:1082')
            self.assertFalse(obj.current_node_verified)

    def test_unknown_listener_provenance_on_old_port_is_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.service(tmp)
            with mock.patch.object(obj,'_inspect_system_route',
                       return_value={'source':'macos_system_proxy','state':'explicit',
                                     'proxy_url':'http://127.0.0.1:1082','endpoint':'127.0.0.1:1082'}), \
                 mock.patch.object(obj,'_inspect_mihomo',return_value={}):
                obj.refresh_active_backend()
            self.assertEqual(obj.active_backend,'system_proxy')

if __name__=='__main__':unittest.main()
