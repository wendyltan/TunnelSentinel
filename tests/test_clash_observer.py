"""Clash interface checks have no route mutations or privacy expansion."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'scripts/clash_observer.py'
spec=importlib.util.spec_from_file_location('clash_observer',p)
clash=importlib.util.module_from_spec(spec);spec.loader.exec_module(clash)

class ClashObserverTests(unittest.TestCase):
    def test_gpt_only_and_no_full_urls(self):
        self.assertTrue(clash.is_gpt_host('ws.chatgpt.com'))
        self.assertTrue(clash.is_gpt_host('api.openai.com'))
        self.assertFalse(clash.is_gpt_host('fakeopenai.com'))
        self.assertFalse(clash.is_gpt_host('gmail.com'))
        with self.assertRaises(ValueError):clash.api('/x','/configs?PUT=1')

    def test_chain_and_simulation_without_switch(self):
        proxies={'proxies':{
            'AI':{'type':'Selector','now':'Proxies','all':['Proxies']},
            'Proxies':{'type':'Selector','now':'nodeA','all':['nodeA','nodeB','quota | 200 G','DIRECT']},
            'nodeA':{'type':'AnyTLS','history':[{'delay':50}]},
            'nodeB':{'type':'AnyTLS','history':[{'delay':120}]},
            'quota | 200 G':{'type':'AnyTLS','history':[{'delay':10}]},
            'DIRECT':{'type':'Direct','history':[{'delay':5}]}
        }}
        connections={'connections':[
            {'metadata':{'host':'ws.chatgpt.com','raw_url':'token-is-private'},'chains':['nodeA','Proxies','AI']},
            {'metadata':{'host':'private.example.com'},'chains':['secret','Proxies','AI']} ]}
        out=clash.summarize({'mode':'rule','tun':{'enable':False}},proxies,connections)
        self.assertEqual(out['active_gpt_connections'],1)
        self.assertEqual(out['active_request_node'],'nodeA')
        self.assertEqual(out['ai_group'],'AI')
        self.assertEqual(out['selected_node'],'nodeA')
        self.assertEqual(out['eligible_count'],2)
        self.assertEqual(out['switch_simulation'],'shared_ai_policy_requires_dedicated_openai_group')
        self.assertFalse(out['switch_write_enabled'])
        self.assertNotIn('token-is-private',str(out))

    def test_inactive_proxy_refuses_observation(self):
        with patch.object(clash,'system_proxy',return_value=('',0)),patch.object(clash,'api') as api:
            result=clash.inspect()
            self.assertFalse(result['active']);api.assert_not_called()

    def test_socket_or_port_mismatch_cannot_claim_clash_ownership(self):
        with patch.object(clash,'system_proxy',return_value=('127.0.0.1',7897)),\
             patch.object(clash,'read_socket_path',return_value='/private/var/folders/fake'),\
             patch.object(clash,'api',return_value={'mixed-port':1099}) as api:
            result=clash.inspect();self.assertFalse(result['active'])
            self.assertEqual(result['reason'],'proxy_port_mismatch')
            self.assertEqual(api.call_count,1)

    def test_mixed_live_request_nodes_are_not_falsely_confirmed(self):
        proxies={'proxies':{'AI':{'type':'Selector','now':'Proxies'},
                            'Proxies':{'type':'Selector','now':'nodeB','all':['nodeA','nodeB']},
                            'nodeA':{'type':'AnyTLS','history':[{'delay':50}]},
                            'nodeB':{'type':'AnyTLS','history':[{'delay':65}]}}}
        connections={'connections':[{'metadata':{'host':'chatgpt.com'},'chains':[node,'Proxies','AI']}
                                    for node in ('nodeA','nodeB','nodeA')]}
        x=clash.summarize({'mode':'rule'},proxies,connections)
        self.assertEqual(x['active_gpt_connections'],3)
        self.assertEqual(x['active_request_node'],'')
        self.assertEqual(x['active_request_chain'],[])

    def test_dedicated_group_wins_and_shared_ai_is_unchanged(self):
        p={'AI':{'type':'Selector','now':'Proxies','all':['Proxies','nodeA']},
           'Proxies':{'type':'Selector','now':'nodeA','all':['nodeA','nodeB']},
           'TunnelSentinel-OpenAI':{'type':'Selector','now':'nodeB','all':['nodeA','nodeB']},
           'nodeA':{'type':'AnyTLS','history':[{'delay':60}]},
           'nodeB':{'type':'AnyTLS','history':[{'delay':100}]}}
        c={'connections':[{'metadata':{'host':'ws.chatgpt.com'},'chains':['nodeB','TunnelSentinel-OpenAI']},
                          {'metadata':{'host':'perplexity.ai'},'chains':['nodeA','Proxies','AI']}]}
        out=clash.summarize({'mode':'rule'},{'proxies':p},c)
        self.assertEqual(out['ai_group'],'TunnelSentinel-OpenAI')
        self.assertEqual(out['selected_node'],'nodeB')
        self.assertEqual(out['active_request_node'],'nodeB')
        self.assertEqual(out['active_gpt_connections'],1)
        self.assertEqual(out['candidate_count'],2)
        self.assertEqual(out['scope'],'dedicated_openai_policy')

    def test_subscriptions_change_does_not_require_hardcoded_nodes(self):
        values={'new-branch':{'type':'Trojan','history':[{'delay':350}]}}
        values['AI']={'type':'Selector','now':'Proxies'}
        values['Proxies']={'type':'Selector','now':'new-branch','all':['new-branch']}
        output=clash.summarize({'mode':'rule'}, {'proxies':values},{'connections':[]})
        self.assertEqual(output['candidate_count'],1)
        self.assertEqual(output['selected_node'],'new-branch')
        self.assertEqual(output['active_request_node'],'')

if __name__=='__main__':unittest.main()
