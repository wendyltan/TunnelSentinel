import json
from pathlib import Path
import tempfile
import unittest
from workflow_health import evaluate, update_timeline, _read

BASE=1_793_030_000
class WorkflowHealthTests(unittest.TestCase):
    def evaluate(self,now=BASE,healthy=True,proxy=True,deep=None,stream=None,issues=None):
        return evaluate(now=now,healthy=healthy,proxy_available=proxy,
                        deep={} if deep is None else deep,
                        stream={} if stream is None else stream,
                        issues=[] if issues is None else issues)

    def test_public_edge_is_never_authenticated_business_success(self):
        r=self.evaluate(deep={'checked_at':BASE,'targets':[{'name':'chatgpt_edge','state':'reachable'}]})
        self.assertEqual(r['network']['state'],'ok')
        self.assertEqual(r['chatgpt']['state'],'partial')
        self.assertEqual(r['codex']['state'],'unknown')
        self.assertEqual(r['computer_use']['state'],'unknown')
    def test_failed_network_never_shows_old_edge_as_reachable(self):
        r=self.evaluate(healthy=False,deep={'checked_at':BASE,'targets':[{'name':'chatgpt_edge','state':'reachable'}]})
        self.assertEqual(r['network']['state'],'failed')
        self.assertEqual(r['chatgpt']['state'],'degraded')

    def test_stale_evidence_is_not_carried_forward(self):
        r=self.evaluate(deep={'checked_at':BASE-700,'targets':[{'name':'chatgpt_edge','state':'reachable'}],
              'real_codex_client':{'state':'ok','routes':[{'status':200,'last_at':BASE-900,'method':'GET','path':'/backend-api/codex/models'}]}})
        self.assertEqual(r['chatgpt']['state'],'partial')  # current primary public GET only
        self.assertEqual(r['chatgpt']['source'],'guardian_public_edge_and_local_proxy')
        self.assertEqual(r['codex']['state'],'unknown')  # stale real client success is NOT reused
    def test_real_model_catalog_is_partial_not_generation(self):
        r=self.evaluate(deep={'checked_at':BASE,'targets':[],
            'real_codex_client':{'state':'ok','routes':[{'status':200,'last_at':BASE-10}],
            'websocket':{'successful_connects':0,'last_success_at':0}}})
        self.assertEqual(r['codex']['state'],'partial')
        self.assertIn('生成未验',r['codex']['label'])
    def test_stream_error_wins_over_catalog_success(self):
        deep={'checked_at':BASE,'real_codex_client':{'state':'ok','routes':[{'status':200,'last_at':BASE-5}]}}
        stream={'state':'ok','recent_counts':{'broken_pipe':2},'last_at':BASE-3}
        r=self.evaluate(deep=deep,stream=stream)
        self.assertEqual(r['codex']['state'],'degraded')
    def test_browser_error_is_not_proof_of_proxy_failure(self):
        r=self.evaluate(issues=[{'category':'browser_backend','last_seen':BASE-2,'count':3}])
        self.assertEqual(r['network']['state'],'ok')
        self.assertEqual(r['computer_use']['state'],'degraded')
    def test_timeline_transition_dedup_restart_and_resolve(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'timeline.json'
            base=self.evaluate()
            a=update_timeline(path,now=BASE,axes=base,proxy_client='shadowrocket',
                              stream={},issues=[],egress_history=[])
            self.assertEqual(a['events'],[])
            bad=self.evaluate(now=BASE+30,healthy=False)
            a=update_timeline(path,now=BASE+30,axes=bad,proxy_client='shadowrocket',
                              stream={},issues=[],egress_history=[])
            self.assertEqual(len([e for e in a['events'] if e['kind']=='incident_started']),1)
            self.assertIsNotNone(a['active_incident'])
            a=update_timeline(path,now=BASE+60,axes=bad,proxy_client='shadowrocket',
                              stream={},issues=[],egress_history=[])
            self.assertEqual(len([e for e in a['events'] if e['kind']=='incident_started']),1)
            a=update_timeline(path,now=BASE+90,axes=base,proxy_client='shadowrocket',
                              stream={},issues=[],egress_history=[])
            self.assertIsNotNone(a['active_incident'])
            a=update_timeline(path,now=BASE+120,axes=base,proxy_client='shadowrocket',
                              stream={},issues=[],egress_history=[])
            self.assertIsNone(a['active_incident'])
            self.assertEqual(len([e for e in a['events'] if e['kind']=='incident_resolved']),1)
    def test_event_markers_ignore_repeat_log_during_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'timeline.json';stamp=BASE-5
            axes=self.evaluate(stream={'state':'ok','recent_counts':{'broken_pipe':2},'last_at':stamp},
                issues=[{'category':'browser_backend','last_seen':stamp,'count':1}])
            for now in (BASE,BASE+30,BASE+60):
                report=update_timeline(path,now=now,axes=axes,proxy_client='shadowrocket',
                   stream={'recent_counts':{'broken_pipe':2},'last_at':stamp},
                   issues=[{'category':'browser_backend','last_seen':stamp}],egress_history=[])
            self.assertEqual(len([e for e in report['events'] if e['kind']=='codex_stream_error']),1)
            self.assertEqual(len([e for e in report['events'] if e['kind']=='client_log_issue']),1)
            self.assertNotIn('token',json.dumps(report).lower())
    def test_only_structured_metadata_no_raw_ip_token(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'timeline.json'
            axes=self.evaluate()
            update_timeline(path,now=BASE,axes=axes,proxy_client='shadowrocket',stream={},issues=[],
                 egress_history=[{'observed_at':'2026-10-26T12:00:00+00:00','ip_before':'PRIVATE_IP','token':'SECRET'}])
            self.assertNotIn('PRIVATE_IP',path.read_text())
            self.assertNotIn('SECRET',path.read_text())
            self.assertEqual(oct(path.stat().st_mode & 0o777),'0o600')

if __name__=='__main__':unittest.main()
