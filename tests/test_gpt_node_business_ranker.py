import unittest
from scripts.gpt_node_business_ranker import assess, recommend

NOW=1793100000
BASE={
    "name":"any-provider-node-X9","policy":"PROXY","profile_id":"current-profile-hash",
    "independent_probe":{
      "source":"mihomo_per_proxy_api","route_confirmed":True,
      "checked_at":NOW-15,"tls_certificate_valid":True,
      "chatgpt_edge_http_code":200,"codex_websocket_host_tls":True
    }
}
class GPTBusinessRankingTests(unittest.TestCase):
 def test_no_candidates_does_not_invent_a_winner(self):
  self.assertIsNone(recommend([],now=NOW,policy='PROXY',profile_id='current-profile-hash')['recommendation'])
 def test_independent_per_node_transport_is_trial_not_business(self):
  x=assess(BASE,now=NOW,policy='PROXY',profile_id='current-profile-hash')
  self.assertEqual(x['verdict'],'trial_candidate')
 def test_group_and_pasted_latencies_are_not_valid_backend_sources(self):
  x=dict(BASE,independent_probe=dict(BASE['independent_probe'],source='manual_shadowrocket_group_latency'))
  self.assertFalse(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['eligible_for_recommendation'])
 def test_absent_route_attribution_is_rejected(self):
  x=dict(BASE,independent_probe=dict(BASE['independent_probe'],route_confirmed=False))
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'unverified')
 def test_old_or_different_profile_is_rejected(self):
  x=dict(BASE,independent_probe=dict(BASE['independent_probe'],checked_at=NOW-601))
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'unverified')
  self.assertEqual(assess(BASE,now=NOW,policy='AI',profile_id='current-profile-hash')['verdict'],'unverified')
 def test_public_http_is_not_real_workflow_success(self):
  x=dict(BASE,real_client_observation={'node':BASE['name'],'profile_id':BASE['profile_id'],
                                       'observed_at':NOW-5,'per_connection_route_proven':True,
                                       'completed_codex_turns':0,'successful_models_catalog_gets':22,
                                       'stable_stream_seconds':0,'client_error_count':0})
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'trial_candidate')
 def test_real_business_requires_route_proof_and_stable_turns(self):
  app={'node':BASE['name'],'profile_id':BASE['profile_id'],
       'observed_at':NOW-5,'per_connection_route_proven':True,
       'completed_codex_turns':2,'stable_stream_seconds':120,'client_error_count':0}
  x=dict(BASE,real_client_observation=app)
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'business_observed')
  x=dict(BASE,real_client_observation=dict(app,per_connection_route_proven=False))
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'trial_candidate')
 def test_real_client_errors_override_openai_connectivity(self):
  app={'node':BASE['name'],'profile_id':BASE['profile_id'],
       'observed_at':NOW-5,'per_connection_route_proven':True,
       'completed_codex_turns':2,'stable_stream_seconds':120,'client_error_count':4}
  x=dict(BASE,real_client_observation=app)
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'not_recommended')
 def test_tls_waffles_or_waf_challenge_disqualifies(self):
  x=dict(BASE,independent_probe=dict(BASE['independent_probe'],chatgpt_edge_http_code=403))
  self.assertEqual(assess(x,now=NOW,policy='PROXY',profile_id='current-profile-hash')['verdict'],'not_recommended')
 def test_business_observation_outranks_only_transport(self):
  x=dict(BASE,real_client_observation={'node':BASE['name'],'profile_id':BASE['profile_id'],
                                       'observed_at':NOW-7,'per_connection_route_proven':True,
                                       'completed_codex_turns':2,'stable_stream_seconds':120,'client_error_count':0})
  y=dict(BASE,name='any-node-B',independent_probe=dict(BASE['independent_probe'],checked_at=NOW))
  r=recommend([y,x],now=NOW,policy='PROXY',profile_id='current-profile-hash')
  self.assertEqual(r['state'],'business_evidence_available')
  self.assertEqual(r['recommendation']['name'],BASE['name'])
if __name__=='__main__':unittest.main()
