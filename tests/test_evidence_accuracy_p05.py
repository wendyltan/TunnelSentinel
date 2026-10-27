"""Evidence provenance, probe timeouts and transient outage display are strict."""
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import openai_link_guardian as guardian
from workflow_health import evaluate
from scripts import gpt_deep_probe as deep


class EvidenceAccuracyP05Tests(unittest.TestCase):
    def axes(self, **kwargs):
        options={"now":1793095000, "healthy":True, "proxy_available":True,
                 "deep":{}, "stream":{}, "issues":[]}
        options.update(kwargs)
        return evaluate(**options)

    def service(self, folder):
        return guardian.Guardian(
            dict(guardian.DEFAULTS), logging.getLogger("accuracy-test"),
            Path(folder)/"status.json")

    def test_deep_timeout_matches_actual_guardian_primary_probe(self):
        self.assertEqual(deep.CONNECT_TIMEOUT_SECONDS,5)
        self.assertEqual(deep.MAX_REQUEST_SECONDS,10)
        self.assertGreater(deep.PROCESS_TIMEOUT_SECONDS,deep.MAX_REQUEST_SECONDS)

    def test_first_failed_network_with_listener_is_verifying(self):
        x=self.axes(healthy=False,network_failure_streak=1)
        self.assertEqual(x["network"]["state"],"partial")
        self.assertIn("复核",x["network"]["label"])
        self.assertEqual(x["chatgpt"]["state"],"partial")

    def test_repeated_failed_network_is_not_hidden(self):
        x=self.axes(healthy=False,network_failure_streak=2)
        self.assertEqual(x["network"]["state"],"failed")
        self.assertEqual(x["chatgpt"]["state"],"degraded")

    def test_missing_proxy_listener_is_immediate_confirmed_failure(self):
        x=self.axes(healthy=False,proxy_available=False,network_failure_streak=1)
        self.assertEqual(x["network"]["state"],"failed")

    def test_primary_success_prevents_anonymous_deep_timeout_false_failure(self):
        now=1793095000
        secondary={"checked_at":now-2,"targets":[{"name":"chatgpt_edge",
                   "state":"transport_failed","http_code":0,"observed_at":now-2}]}
        x=self.axes(deep=secondary)
        self.assertEqual(x["network"]["state"],"ok")
        self.assertEqual(x["chatgpt"]["state"],"partial")
        self.assertIn("深层抽样超时",x["chatgpt"]["label"])
        self.assertNotEqual(x["chatgpt"]["state"],"degraded")

    def test_deep_success_is_not_authenticated_chatgpt(self):
        x=self.axes(deep={"checked_at":1793095000,"targets":[
            {"name":"chatgpt_edge","state":"reachable","observed_at":1793094999}]})
        self.assertEqual(x["chatgpt"]["state"],"partial")
        self.assertEqual(x["chatgpt"]["observed_at"],1793094999)

    def test_business_status_no_authenticated_success_maintains_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            obj=self.service(td)
            obj.write_status([guardian.ProbeResult("edge",True,200,False,.2)],0,True)
            data=json.loads((Path(td)/"status.json").read_text())
            self.assertEqual(data["business_status"],"unverified")
            self.assertEqual(data["overall_status"],"reachable")
            self.assertIn("no_authenticated",data["business_evidence_scope"])

    def test_first_failed_probe_status_verifying_not_offline(self):
        with tempfile.TemporaryDirectory() as td:
            obj=self.service(td)
            obj.write_status([guardian.ProbeResult("edge",False,0,False,10.0)],0,False,
                             proxy_available=True,network_failure_streak=1)
            data=json.loads((Path(td)/"status.json").read_text())
            self.assertEqual(data["overall_status"],"verifying")
            self.assertEqual(data["workflow_health"]["network"]["state"],"partial")
            self.assertEqual(data["business_status"],"unverified")
            self.assertEqual(data["probes"][0]["http_code"],0) # raw measurement still recorded

    def test_historical_good_candidates_are_not_GPT_verified(self):
        with tempfile.TemporaryDirectory() as td:
            obj=self.service(td)
            obj.learned_good_nodes=["Node from prior public edge probes"]
            obj.known_good_cache_updated_at=guardian.time.monotonic()
            obj.write_status([guardian.ProbeResult("edge",True,200,False,.2)],0,True)
            data=json.loads((Path(td)/"status.json").read_text())
            self.assertIn("http200_only",data["known_good_candidates_scope"])
            self.assertEqual(data["historical_public_edge_nodes"],
                             ["Node from prior public edge probes"])

    def test_ui_has_per_axis_provenance_and_debounce_ui(self):
        src=Path(__file__).resolve().parents[1]/"menubar/TunnelSentinelMenu.swift"
        text=src.read_text()
        self.assertIn("测于",text)
        self.assertIn("深层探测采样：",text)
        self.assertIn("单次超时 · 复核中",text)
        self.assertIn("取自 Codex 只读日志",text)
        self.assertIn("networkReviewPending",text)

if __name__=="__main__":
    unittest.main()
