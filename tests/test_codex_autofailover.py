import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("codex_autofailover",ROOT/"scripts/codex_autofailover.py")
route=importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)

class AutoRecoveryTests(unittest.TestCase):
    def snapshot(self,now,failures=4,lag=4,healthy=True):
        return {
            "healthy":healthy,"route_management":"native_fallback",
            "native_fallback_group":"OpenAI-Resilience",
            "codex_stream_diagnostics":{
                "state":"ok","scan_at":now,"last_at":now-lag,
                "recent_counts":{"broken_pipe":failures,"websocket_handshake":0,
                                 "connection_reset":0},
            },
        }
    def test_original_policy_matches_native_group(self):
        self.assertEqual(route.ORIGINAL,"(?i)(JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07)")
        self.assertEqual(route.rule_for(["JAPAN 14"]),
            "(?i)(JAPAN 04|SEATTLE 05|SAN JOSE 07)")
        self.assertEqual(route.rule_for(["JAPAN 14","SEATTLE 05"]),
            "(?i)(JAPAN 04|SAN JOSE 07)")
        with self.assertRaises(ValueError):
            route.rule_for(["JAPAN 14","SEATTLE 05","JAPAN 04"])
    def test_parse_real_native_ui_node(self):
        self.assertEqual(route.parse_node("CURRENT_GROUP_NODE 🇯🇵 JAPAN 14"),"JAPAN 14")
        self.assertEqual(route.parse_node("CURRENT_GROUP_NODE 🇺🇸 USA SEATTLE 05"),"SEATTLE 05")
        self.assertIsNone(route.parse_node("CURRENT_GROUP_NODE other"))
        self.assertIsNone(route.parse_node("GLOBAL_NODE 🇯🇵 JAPAN 14"))
    def test_trigger_strict_window(self):
        now=int(time.time())
        good=self.snapshot(now)
        self.assertEqual(route.decision(good["codex_stream_diagnostics"],route.default_state(),now),
                         (True,"qualified_stream_failure"))
        for num,delay in [(2,2),(9,230)]:
            p=self.snapshot(now,num,delay)
            self.assertIsNone(route.decision(p["codex_stream_diagnostics"],route.default_state(),now)[0])
        p=self.snapshot(now);p["codex_stream_diagnostics"]["scan_at"]=now-1000
        self.assertEqual(route.decision(p["codex_stream_diagnostics"],route.default_state(),now)[1],
                         "stale_codex_scan")
    def test_cooldown_daily_limit_and_two_node_floor(self):
        now=int(time.time());st=route.default_state()
        st["last_attempt_at"]=now-60
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],"cooldown")
        st["last_attempt_at"]=0;st["actions_today"]=3
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],"daily_limit")
        st["actions_today"]=0;st["excluded"]=["JAPAN 14","SEATTLE 05"]
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],
                         "candidate_safety_limit")
    def test_healthy_probe_never_edit_without_codex_error(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route,"current_node") as node, mock.patch.object(route,"run_editor") as editor:
            out=route.apply_transition(self.snapshot(now,failures=0),st,now=now)
            node.assert_not_called();editor.assert_not_called()
        self.assertEqual(out["reason"],"insufficient_errors")
    def test_real_selected_japan14_is_excluded_not_seattle(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route,"current_node",return_value=("JAPAN 14","ok")) as node, \
             mock.patch.object(route,"run_editor",return_value=(True,"saved_and_reopened")) as edit:
            out=route.apply_transition(self.snapshot(now),st,now=now)
        self.assertEqual(out["state"],"policy_updated_awaiting_backend_evidence")
        self.assertEqual(out["excluded_node"],"JAPAN 14")
        self.assertEqual(st["excluded"],["JAPAN 14"])
        self.assertEqual(st["previous_node"],"JAPAN 14")
        self.assertFalse(st["last_backend_verified"])
        edit.assert_called_once_with(route.rule_for(["JAPAN 14"]),route.ORIGINAL,route.APP)
    def test_pending_verification_waits_for_different_allowed_node(self):
        now=int(time.time());st=route.default_state()
        st.update(status="policy_updated_awaiting_backend_evidence",excluded=["JAPAN 14"],
                  phase=1,rule=route.rule_for(["JAPAN 14"]),previous_node="JAPAN 14",
                  last_transition_at=now-60)
        with mock.patch.object(route,"current_node",return_value=("JAPAN 14","ok")) as get, \
             mock.patch.object(route,"run_editor") as edit:
            out=route.apply_transition(self.snapshot(now),st,now=now)
            self.assertEqual(out["state"],"policy_updated_awaiting_backend_evidence")
            edit.assert_not_called()
        with mock.patch.object(route,"current_node",return_value=("SEATTLE 05","ok")):
            out=route.apply_transition(self.snapshot(now),st,now=now+1)
        self.assertEqual(out["state"],"armed")
        self.assertTrue(st["last_backend_verified"])
        self.assertEqual(st["selected_node"],"SEATTLE 05")
    def test_pending_unverified_times_out_without_extra_switch(self):
        now=int(time.time());st=route.default_state()
        st.update(status="policy_updated_awaiting_backend_evidence",excluded=["JAPAN 14"],
                  last_transition_at=now-190)
        with mock.patch.object(route,"current_node",return_value=(None,"not_visible")), \
             mock.patch.object(route,"run_editor") as edit:
            result=route.apply_transition(self.snapshot(now),st,now=now)
            edit.assert_not_called()
        self.assertEqual(result["state"],"backend_unverified")
        with mock.patch.object(route,"run_editor") as edit:
            result=route.apply_transition(self.snapshot(now),st,now=now+15)
            edit.assert_not_called()
        self.assertEqual(result["reason"],"manual_review_required")
    def test_untrusted_controller_rejected_without_state_advance(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route,"current_node",return_value=(None,"group_not_visible_or_access_denied")), \
             mock.patch.object(route,"run_editor") as edit:
            result=route.apply_transition(self.snapshot(now),st,now=now)
            edit.assert_not_called()
        self.assertEqual(result["state"],"controller_unavailable")
        self.assertEqual(st["phase"],0)
    def test_failed_save_disables_repeated_triggers(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route,"current_node",return_value=("JAPAN 14","ok")), \
             mock.patch.object(route,"run_editor",return_value=(False,"save_not_confirmed")):
            result=route.apply_transition(self.snapshot(now),st,now=now)
        self.assertEqual(result["state"],"controller_unavailable")
        self.assertEqual(st["excluded"],[])
        with mock.patch.object(route,"run_editor") as edit:
            route.apply_transition(self.snapshot(now),st,now=now+700)
            edit.assert_not_called()
    def test_rollback_once_after_public_unhealthy(self):
        now=int(time.time());st=route.default_state()
        st.update(status="policy_updated_awaiting_backend_evidence",
                  excluded=["JAPAN 14"],phase=1,
                  rule=route.rule_for(["JAPAN 14"]),previous_rule=route.ORIGINAL,
                  previous_node="JAPAN 14",last_transition_at=now-30)
        with mock.patch.object(route,"run_editor",return_value=(True,"saved_and_reopened")) as edit:
            out=route.apply_transition(self.snapshot(now,healthy=False),st,now=now)
            edit.assert_called_once_with(route.ORIGINAL,route.rule_for(["JAPAN 14"]),route.APP)
        self.assertEqual(out["state"],"rolled_back_after_public_failure")
        self.assertEqual(st["excluded"],[])
        with mock.patch.object(route,"run_editor") as edit:
            route.apply_transition(self.snapshot(now,healthy=False),st,now=now+1)
            edit.assert_not_called()
    def test_invalid_group_or_public_failure_prevents_forward_change(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route,"run_editor") as editor:
            bad=self.snapshot(now);bad["native_fallback_group"]="Other"
            self.assertEqual(route.apply_transition(bad,st,now=now)["state"],"disabled")
            self.assertEqual(route.apply_transition(self.snapshot(now,healthy=False),st,now=now)["state"],"suppressed")
            editor.assert_not_called()
    def test_explicit_config_gate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"config.json"
            cfg={"native_fallback_enabled":True,"native_fallback_group":"OpenAI-Resilience",
                 "codex_stream_sqlite_monitor_enabled":True,"codex_auto_failover_enabled":False}
            p.write_text(json.dumps(cfg))
            self.assertFalse(route.enabled(p))
            cfg["codex_auto_failover_enabled"]=True
            p.write_text(json.dumps(cfg))
            self.assertTrue(route.enabled(p))
            cfg["native_fallback_group"]="Other"
            p.write_text(json.dumps(cfg))
            self.assertFalse(route.enabled(p))
    def test_background_preflight_does_not_attempt_node_changes(self):
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/"config.json";result=Path(d)/"preflight.json"
            c.write_text(json.dumps({"codex_auto_preflight_enabled":True}))
            outcomes=[
                mock.Mock(returncode=0,stdout="ACCESSIBILITY=granted EVENT_CONTROL=granted"),
                mock.Mock(returncode=0,stdout="CURRENT_GROUP_NODE 🇯🇵 JAPAN 14"),
            ]
            with mock.patch.object(route.subprocess,"run",side_effect=outcomes) as sp:
                route.background_preflight(c,result,route.APP)
            report=json.loads(result.read_text())
            self.assertEqual(report["controller_access"],"granted")
            self.assertEqual(report["node"],"JAPAN 14")
            self.assertEqual(report["native_group_ui"],"readable")
            self.assertEqual(len(sp.call_args_list),2)
            self.assertTrue(all("--set" not in str(c) for c in sp.call_args_list))

    def test_preflight_disabled_does_not_launch_controller(self):
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/"config.json";o=Path(d)/"out.json"
            c.write_text(json.dumps({"codex_auto_preflight_enabled":False}))
            with mock.patch.object(route.subprocess,"run") as sp:
                self.assertEqual(route.background_preflight(c,o),0)
                sp.assert_not_called()
            self.assertFalse(o.exists())

    def test_nonconcurrent_lock_and_privacy(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"status.json"
            st=route.default_state()
            st["selected_node"]="JAPAN 04"
            with route.single_writer(p) as first:
                self.assertTrue(first)
                with route.single_writer(p) as other:
                    self.assertFalse(other)
            route.persist(st,p)
            self.assertEqual(route.load_state(p)["selected_node"],"JAPAN 04")
            self.assertNotIn("token",p.read_text())
            self.assertNotIn("prompt",p.read_text())

if __name__=="__main__":
    unittest.main()
