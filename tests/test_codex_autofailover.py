import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("codex_autofailover",ROOT/"scripts/codex_autofailover.py")
route=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(route)

class CodexAutoFailoverTests(unittest.TestCase):
    def snapshot(self,now, count=4,latest_offset=3, healthy=True):
        return {"route_management":"native_fallback",
                "native_fallback_group":"OpenAI-Resilience","healthy":healthy,
                "codex_stream_diagnostics":{"state":"ok","counts":{
                    "broken_pipe":count,"websocket_handshake":0,"connection_reset":0},
                    "last_at":now-latest_offset,
                    "scan_at":now,
                    "recent_counts":{"broken_pipe":count,
                                     "websocket_handshake":0,
                                     "connection_reset":0}}}
    def test_recent_repeated_broken_pipe_qualifies(self):
        now=int(time.time())
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],
                                        route.default_state(),now),(1,"qualified_stream_failure"))
    def test_no_change_for_stale_single_or_duplicate_error(self):
        now=int(time.time())
        for count,offset in [(1,3),(9,220)]:
            p,r=route.decision(self.snapshot(now,count,offset)["codex_stream_diagnostics"],
                               route.default_state(),now)
            self.assertIsNone(p)
        st=route.default_state()
        st["last_trigger_at"]=now-3
        p,r=route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)
        self.assertEqual(r,"already_handled")
    def test_old_30min_errors_cannot_trigger_with_one_new_error(self):
        now=int(time.time())
        scan=self.snapshot(now,count=9)["codex_stream_diagnostics"]
        scan["recent_counts"]={"broken_pipe":1,"websocket_handshake":0,"connection_reset":0}
        step,why=route.decision(scan,route.default_state(),now)
        self.assertIsNone(step)
        self.assertEqual(why,"insufficient_errors")

    def test_stale_codex_read_cannot_trigger(self):
        now=int(time.time())
        scan=self.snapshot(now)["codex_stream_diagnostics"]
        scan["scan_at"]=now-200
        self.assertEqual(route.decision(scan,route.default_state(),now)[1],"stale_codex_scan")

    def test_unverified_transition_prevents_second_exclusion(self):
        now=int(time.time());state=route.default_state()
        state["phase"]=1
        state["status"]="policy_updated_awaiting_backend_evidence"
        state["last_attempt_at"]=now-3600
        with mock.patch.object(route.subprocess,"run") as run:
            result=route.apply_transition(self.snapshot(now),state,now=now)
            run.assert_not_called()
        self.assertEqual(result["phase"],1)
        self.assertEqual(result["reason"],"awaiting_verification_or_explicit_recovery")

    def test_strict_stage_cooldown_and_daily_limit(self):
        now=int(time.time())
        st=route.default_state();st["phase"]=1
        st["last_attempt_at"]=now-15
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],"cooldown")
        st["last_attempt_at"]=0;st["actions_today"]=3
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],"daily_limit")
        st["actions_today"]=0;st["phase"]=3
        self.assertEqual(route.decision(self.snapshot(now)["codex_stream_diagnostics"],st,now)[1],"candidates_exhausted")
    def test_no_global_change_and_backend_unverified(self):
        now=int(time.time())
        st=route.default_state()
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/"helper"
            binary.write_text("placeholder")
            with mock.patch.object(route.subprocess,"run",return_value=mock.Mock(returncode=0,stdout="SAVED")) as cmd:
                result=route.apply_transition(self.snapshot(now),st,exe=binary,now=now)
            self.assertEqual(result["state"],"policy_updated_awaiting_backend_evidence")
            self.assertFalse(result["backend_verified"])
            self.assertEqual(st["phase"],1)
            command=cmd.call_args.args[0]
            self.assertEqual(command[1],"--set")
            self.assertEqual(command[2],route.PHASES[1])
            self.assertEqual(command[4],route.PHASES[0])
            self.assertNotIn("shadowrocket://select",str(command))
            self.assertNotIn("route/proxy",str(command))
    def test_permission_denial_does_not_advance_phase(self):
        now=int(time.time());st=route.default_state()
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/"helper";binary.touch()
            with mock.patch.object(route.subprocess,"run",return_value=mock.Mock(returncode=77)) as cmd:
                out=route.apply_transition(self.snapshot(now),st,exe=binary,now=now)
            self.assertEqual(out["state"],"permission_or_ui_blocked")
            self.assertEqual(st["phase"],0)
            self.assertEqual(st["actions_today"],0)
    def test_failed_public_route_rolls_back_one_phase_once(self):
        now=int(time.time());st=route.default_state()
        st["phase"]=1;st["last_transition_at"]=now-20
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/"helper";binary.touch()
            with mock.patch.object(route.subprocess,"run",return_value=mock.Mock(returncode=0)) as cmd:
                out=route.apply_transition(self.snapshot(now,healthy=False),st,exe=binary,now=now)
            self.assertEqual(out["state"],"rolled_back_after_public_failure")
            self.assertEqual(st["phase"],0)
            self.assertEqual(cmd.call_args.args[0][2],route.PHASES[0])
            out=route.apply_transition(self.snapshot(now,healthy=False),st,exe=binary,now=now+2)
            self.assertEqual(out["reason"],"public_edge_down")

    def test_disabled_wrong_group_never_executes(self):
        now=int(time.time());st=route.default_state()
        with mock.patch.object(route.subprocess,"run") as runner:
            p=self.snapshot(now);p["native_fallback_group"]="Other"
            self.assertEqual(route.apply_transition(p,st,now=now)["state"],"disabled")
            runner.assert_not_called()
    def test_explicit_config_gate_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"config.json"
            x={"native_fallback_enabled":True,
               "native_fallback_group":"OpenAI-Resilience",
               "codex_stream_sqlite_monitor_enabled":True,
               "codex_auto_failover_enabled":False}
            p.write_text(json.dumps(x))
            self.assertFalse(route.enabled(p))
            x["codex_auto_failover_enabled"]=True
            p.write_text(json.dumps(x))
            self.assertTrue(route.enabled(p))
            x["native_fallback_group"]="Other"
            p.write_text(json.dumps(x))
            self.assertFalse(route.enabled(p))

    def test_reentrant_tasks_do_not_overlap_route_edit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json"
            with route.nonconcurrent(path) as first:
                self.assertTrue(first)
                with route.nonconcurrent(path) as second:
                    self.assertFalse(second)
            with route.nonconcurrent(path) as later:
                self.assertTrue(later)

    def test_status_on_disk_contains_no_codex_prompt_or_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json"
            st=route.default_state()
            st["status"]="permission_or_ui_blocked"
            route.persist(st,path)
            data=json.loads(path.read_text())
            self.assertEqual(data["status"],"permission_or_ui_blocked")
            self.assertNotIn("prompt",path.read_text().lower())
