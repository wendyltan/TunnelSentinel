"""Passive OpenAI egress transitions. No live proxies or Shadowrocket reads."""
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import openai_link_guardian as guardian


def sample(ip, country="US", colo="SEA"):
    return guardian.ProbeResult("edge", True, 200, False, .1, "", ip, colo, country)


class EgressHistoryTests(unittest.TestCase):
    def new_guardian(self, path):
        with mock.patch.object(guardian, "current_shadowrocket_node", return_value=None):
            return guardian.Guardian(
                dict(guardian.DEFAULTS, native_fallback_enabled=True),
                logging.getLogger("passive-egress-history"),
                path,
            )

    def test_two_good_samples_required_for_baseline_and_changed_exit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "status.json"
            service = self.new_guardian(path)
            one, two = sample("192.0.2.1"), sample("198.51.100.2", "JP", "NRT")
            service.observe_edge_incident([one], True)
            self.assertEqual(service.egress_changed_at, [])
            service.observe_edge_incident([one], True)
            self.assertEqual(service.egress_changed_at, [])
            service.observe_edge_incident([two], True)
            self.assertEqual(service.egress_changed_at, [])
            service.observe_edge_incident([two], True)
            service.write_status([two], 0, True)
            state = json.loads(path.read_text())
            event, = state["egress_change_history"]
            self.assertEqual(event["egress_before"], "192.0.2.1")
            self.assertEqual(event["egress_after"], "198.51.100.2")
            self.assertEqual(event["geo_after"], "JP-NRT")
            self.assertEqual(event["confirmation"], "2_consecutive_healthy_probes")
            self.assertFalse(event["native_backend_switch_verified"])
            self.assertEqual(event["evidence"], "confirmed_public_edge_egress_change")

    def test_flapping_one_off_ip_and_failed_probe_never_emits_event(self):
        with tempfile.TemporaryDirectory() as d:
            service = self.new_guardian(Path(d) / "status.json")
            a,b=sample("192.0.2.1"),sample("198.51.100.2")
            service.observe_edge_incident([a],True)
            service.observe_edge_incident([a],True)
            service.observe_edge_incident([b],True)
            service.observe_edge_incident([a],True)
            service.observe_edge_incident([b],True)
            service.observe_edge_incident([guardian.ProbeResult("edge",False,0,False,4)],False)
            service.observe_edge_incident([b],True)
            self.assertEqual(service.egress_changed_at, [])

    def test_egress_after_recovery_marks_association_not_native_switch(self):
        with tempfile.TemporaryDirectory() as d:
            service=self.new_guardian(Path(d)/"status.json")
            a,b=sample("192.0.2.1"),sample("198.51.100.2")
            service.observe_edge_incident([a],True)
            service.observe_edge_incident([a],True)
            bad=guardian.ProbeResult("edge",False,0,False,10)
            service.observe_edge_incident([bad],False)
            service.observe_edge_incident([b],True)
            service.observe_edge_incident([b],True)
            self.assertEqual(len(service.egress_changed_at),1)
            change=service.egress_changed_at[0]
            self.assertTrue(change["preceded_by_recent_public_outage"])
            self.assertFalse(change["native_backend_switch_verified"])

    def test_recent_history_is_bounded_across_restarts(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"status.json"
            service=self.new_guardian(path)
            for i in range(9):
                r=sample(f"192.0.2.{i+1}")
                service.observe_edge_incident([r],True)
                service.observe_edge_incident([r],True)
            service.write_status([sample("192.0.2.9")],0,True)
            self.assertEqual(len(service.egress_changed_at),6)
            restart=self.new_guardian(path)
            self.assertEqual(len(restart.egress_changed_at),6)
            self.assertIsNone(restart.confirmed_egress)
            restart.observe_edge_incident([sample("192.0.2.10")],True)
            restart.observe_edge_incident([sample("192.0.2.10")],True)
            self.assertEqual(len(restart.egress_changed_at),6)
