"""Codex stream diagnostics are independent of public edge and failover."""
import importlib.util
import json
import logging
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest import mock
import openai_link_guardian as guardian

SPEC=importlib.util.spec_from_file_location(
    "codex_stream_monitor", Path(__file__).resolve().parents[1]/"scripts/codex_stream_health.py")
health=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)

class CodexStreamTests(unittest.TestCase):
    def new_guardian(self,d):
        config=dict(guardian.DEFAULTS,native_fallback_enabled=True,
                    native_fallback_group="OpenAI-Resilience",
                    codex_stream_sqlite_monitor_enabled=True)
        with mock.patch.object(guardian,"current_shadowrocket_node",return_value=None):
            return guardian.Guardian(config,logging.getLogger("codex-stream-unit"),
                                     Path(d)/"status.json")

    def test_scan_only_known_network_targets_and_no_body_exposure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"codex.sqlite"
            c=sqlite3.connect(p)
            c.execute("create table logs(id integer primary key,ts integer,target text, feedback_log_body text)")
            now=int(time.time())
            c.executemany("insert into logs(ts,target,feedback_log_body) values (?,?,?)",[
                (now-5,"codex_core::responses_retry","stream disconnected before completion: IO error: Broken pipe (os error 32); SECRET_PROMPT"),
                (now-5,"codex_api::endpoint::responses_websocket","websocket handshake failed; SECRET_KEY"),
                (now-5,"codex_core::responses_retry","stream disconnected: connection reset by peer"),
                (now-5,"other_target","broken pipe account sensitive"),
                (now-3900,"codex_core::responses_retry","Broken pipe old"),
            ])
            c.commit();c.close()
            out=health.scan(p,now)
            self.assertEqual(out["counts"],{"broken_pipe":1,"websocket_handshake":1,"connection_reset":1})
            self.assertEqual(out["last_at"],now-5)
            self.assertEqual(out["recent_counts"],out["counts"])
            self.assertNotIn("SECRET_PROMPT",json.dumps(out))
            self.assertNotIn("SECRET_KEY",json.dumps(out))
            self.assertNotIn("account sensitive",json.dumps(out))

    def test_missing_db_is_unavailable_not_healthy(self):
        with tempfile.TemporaryDirectory() as d:
            x=health.scan(Path(d)/"missing.sqlite")
            self.assertEqual(x["state"],"unavailable")

    def test_guard_status_is_attention_but_never_calls_switch(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.new_guardian(d)
            now=int(time.time())
            svc.codex_stream_result={"state":"ok","source":"codex_read_only_sqlite",
                                     "counts":{"broken_pipe":3,"websocket_handshake":1,"connection_reset":0},
                                     "last_at":now,"scan_at":now}
            good=guardian.ProbeResult("edge",True,200,False,.25)
            with mock.patch.object(svc,"attempt_failover") as action:
                svc.write_status([good],0,True)
                action.assert_not_called()
            data=json.loads((Path(d)/"status.json").read_text())
            self.assertTrue(data["healthy"])
            self.assertEqual(data["overall_status"],"attention")
            self.assertEqual(data["business_status"],"attention")
            self.assertEqual(data["business_issues"][0]["category"],"codex_stream")

    def test_old_errors_expire_without_changing_network_health(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.new_guardian(d)
            now=int(time.time())
            svc.codex_stream_result={"state":"ok","counts":{"broken_pipe":4},"last_at":now-1900}
            good=guardian.ProbeResult("edge",True,200,False,.25)
            svc.write_status([good],0,True)
            data=json.loads((Path(d)/"status.json").read_text())
            self.assertEqual(data["overall_status"],"reachable")
            self.assertFalse(data["business_issues"])

    def test_disabled_monitor_never_starts_worker(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.new_guardian(d)
            svc.config["codex_stream_sqlite_monitor_enabled"]=False
            with mock.patch.object(guardian.threading,"Thread") as t:
                svc.maybe_begin_codex_stream()
                t.assert_not_called()
