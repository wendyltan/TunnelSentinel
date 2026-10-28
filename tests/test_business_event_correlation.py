"""Two independent local timestamps can correlate but cannot prove cause."""
import unittest
import openai_link_guardian as g

class BusinessEvidenceTests(unittest.TestCase):
 def test_nearby_real_sources_only(self):
  t=1800000000
  stream={'state':'ok','last_at':t-40,'recent_counts':{'broken_pipe':1}}
  tool={'execution':{'state':'ok','latest_at':t-20,'latest_status':'completed'}}
  result=g.correlate_client_events(stream,tool,t)
  self.assertEqual(result['state'],'nearby_events')
  self.assertEqual(result['gap_seconds'],20)
  self.assertNotIn('task_success',str(result))
 def test_stale_and_unavailable_not_claimed(self):
  t=1800000000
  stream={'state':'ok','last_at':t-1900,'recent_counts':{'broken_pipe':1}}
  tool={'execution':{'state':'ok','latest_at':t-25}}
  self.assertNotEqual(g.correlate_client_events(stream,tool,t)['state'],'nearby_events')
  self.assertEqual(g.correlate_client_events({},tool,t)['state'],'unverified')
 def test_different_event_window_no_shared_task_claim(self):
  t=1800000000
  stream={'state':'ok','last_at':t-500,'recent_counts':{'connection_reset':1}}
  tool={'execution':{'state':'ok','latest_at':t-2}}
  self.assertEqual(g.correlate_client_events(stream,tool,t)['state'],'no_recent_overlap')
