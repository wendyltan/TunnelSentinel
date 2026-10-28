import unittest
import tempfile
from pathlib import Path
from datetime import date
from scripts.shadowrocket_failover_preflight import assess,daily_log_summary

NOW=1793160000
GROUP="OpenAI-Resilience"
CONFIG={"native_fallback_enabled":True,"native_fallback_group":GROUP}
STATUS={"proxy_client":"shadowrocket","native_group_route_verified":False,
        "native_proxy_log_recent":False}
AUDIT={"state":"verified_rule_matches","checked_at":NOW-30,"rules":[
    {"host":h,"policy":GROUP} for h in
    ("chatgpt.com","ws.chatgpt.com","api.openai.com")]}

class FailoverPreflightTests(unittest.TestCase):
    def test_group_found_is_not_failover_or_node_proof(self):
        x=assess(CONFIG,STATUS,AUDIT,now=NOW)
        self.assertTrue(x["audited_rule_match"])
        self.assertFalse(x["native_failover_confirmed"])
        self.assertIsNone(x["manual_node_recommendation"])
        self.assertFalse(x["autonomous_route_write_safe"])

    def test_stale_audit_is_blocker_even_if_match(self):
        x=assess(CONFIG,STATUS,dict(AUDIT,checked_at=NOW-601),now=NOW)
        self.assertEqual(x["routing_gate"],"rule_audit_missing_or_stale")

    def test_proxy_policy_does_not_pass_group_gate(self):
        rows=[dict(r,policy="PROXY") for r in AUDIT["rules"]]
        x=assess(CONFIG,STATUS,dict(AUDIT,rules=rows),now=NOW)
        self.assertEqual(x["routing_gate"],"required_openai_rules_do_not_match_fallback_group")

    def test_partial_domain_match_does_not_pass(self):
        rows=AUDIT["rules"][:2]
        x=assess(CONFIG,STATUS,dict(AUDIT,rules=rows),now=NOW)
        self.assertFalse(x["audited_rule_match"])

    def test_unknown_backend_and_missing_group_block(self):
        self.assertEqual(assess(CONFIG,dict(STATUS,proxy_client="other"),AUDIT,now=NOW)["routing_gate"],
                         "current_system_proxy_is_not_shadowrocket")
        self.assertEqual(assess(dict(CONFIG,native_fallback_enabled=False),STATUS,AUDIT,now=NOW)["routing_gate"],
                         "native_group_not_configured")

    def test_global_node_and_egress_never_create_candidate(self):
        status=dict(STATUS,current_node="USA Seattle 07",current_node_verified=True,
                    egress_country="US",native_group_route_verified=True,native_proxy_log_recent=True)
        x=assess(CONFIG,status,AUDIT,now=NOW)
        self.assertIsNone(x["manual_node_recommendation"])
        self.assertFalse(x["native_failover_confirmed"])

    def test_counts_only_non_sensitive_and_current_day(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"guardian.log"
            p.write_text("2026-10-28 03:22 INFO health=ok node=ONE score=0 probes=edge:200:ok\n"
                         "2026-10-28 03:23 INFO health=bad node=ONE score=0 probes=edge-retry:0:bad\n"
                         "2026-10-28 03:24 WARNING public edge reachable again sampled_outage_s=14\n"
                         "2026-10-28 03:25 INFO public edge egress changed; 2 healthy probes confirmed\n"
                         "2026-10-28 04:00 INFO health=ok node=TWO score=0 probes=edge:200:ok\n")
            r=daily_log_summary(p,day=date(2026,10,28))
            self.assertEqual(r["public_probe_samples"],3)
            self.assertEqual(r["public_probe_bad"],1)
            self.assertEqual(r["confirmed_egress_region_changes"],1)
            self.assertEqual(r["global_node_label_transitions"],1)
            self.assertNotIn("ONE",str(r))

if __name__=="__main__": unittest.main()
