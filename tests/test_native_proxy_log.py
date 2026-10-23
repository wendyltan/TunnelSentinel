"""Privacy-safe native Shadowrocket proxy log reading tests."""
import importlib.util
import json
import logging
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

import openai_link_guardian as guard

HELPER=Path(__file__).resolve().parents[1]/"scripts/shadowrocket_native_log_probe.py"
spec=importlib.util.spec_from_file_location("native_probe",HELPER)
native=importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeRouteReaderTests(unittest.TestCase):
    def test_parses_genuine_route_and_filters_others(self):
        row=native.parse_route(
            "ws.chatgpt.com:443",
            "DOMAIN-SUFFIX,chatgpt.com,OpenAI-Resilience # 🇺🇸 USA Seattle 05",
            "2026-10-23 19:16:32","OpenAI-Resilience")
        self.assertEqual(row["name"],"🇺🇸 USA Seattle 05")
        self.assertEqual(row["host"],"ws.chatgpt.com")
        self.assertNotIn("url",row)
        self.assertNotIn("ua",row)
        self.assertIsNone(native.parse_route(
            "notchatgpt.com:443",
            "DOMAIN-SUFFIX,chatgpt.com,OpenAI-Resilience # Other",
            "2026-10-23 19:16:32","OpenAI-Resilience"))
        self.assertIsNone(native.parse_route(
            "other.com:443",
            "FINAL,PROXY # 🇯🇵 Japan 04",
            "2026-10-23 19:16:32","OpenAI-Resilience"))
        self.assertIsNone(native.parse_route(
            "chatgpt.com:443",
            "DOMAIN-SUFFIX,chatgpt.com,OtherGroup # Other",
            "2026-10-23 19:16:32","OpenAI-Resilience"))

    def test_sanitized_schema_and_newest_native_node(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"proxy-test.db"
            c=sqlite3.connect(p)
            c.execute("CREATE TABLE logging_content(docid INTEGER PRIMARY KEY,c0url TEXT,c1ua TEXT,c2result TEXT,c3type TEXT,c4created TEXT)")
            data=[
                ("mail.example.com:443","personal-login-code-XYZ","FINAL,PROXY # Secret subscription","HTTPS","2026-10-23 19:16:10"),
                ("chatgpt.com:443","hidden-UA-and-cookies","DOMAIN-SUFFIX,chatgpt.com,OpenAI-Resilience # 🇺🇸 USA Seattle 05","PROXY","2026-10-23 19:16:20"),
                ("ws.chatgpt.com:443","private-UA","DOMAIN-SUFFIX,chatgpt.com,OpenAI-Resilience # 🇯🇵 Japan 14","PROXY","2026-10-23 19:16:40")]
            c.executemany("INSERT INTO logging_content(c0url,c1ua,c2result,c3type,c4created) VALUES (?,?,?,?,?)",data)
            c.commit();c.close()
            out=native.scan_logs(Path(folder),"OpenAI-Resilience")
            self.assertEqual(out["latest"]["name"],"🇯🇵 Japan 14")
            self.assertEqual(len(out["samples"]),2)
            safe=json.dumps(out,ensure_ascii=False)
            for secret in ("personal-login-code","hidden-UA","private-UA","Secret subscription","mail.example.com"):
                self.assertNotIn(secret,safe)

    def test_missing_database_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(native.scan_logs(Path(d),"OpenAI-Resilience")["latest"])

    def guardian(self,d,enabled=True):
        cfg=dict(guard.DEFAULTS)
        cfg["native_fallback_enabled"]=True
        cfg["native_fallback_group"]="OpenAI-Resilience"
        cfg["native_proxy_log_reader_enabled"]=enabled
        with mock.patch.object(guard,"current_shadowrocket_node",return_value=None):
            return guard.Guardian(cfg,logging.getLogger("native-log-tests"),Path(d)/"status.json")

    def test_guardian_consumes_only_named_evidence_and_expires(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.guardian(d)
            now=int(time.time())
            def report(node="🇺🇸 USA Seattle 05",dt=0):
                return {"source":"shadowrocket_native_proxy_log",
                        "group":"OpenAI-Resilience",
                        "latest":{"source":"shadowrocket_native_proxy_log","group":"OpenAI-Resilience",
                                  "name":node,"host":"chatgpt.com",
                                  "epoch":now+dt,"observed_at":"2026-10-23T19:16:40+08:00"},
                        "samples":[]}
            proc=mock.Mock(returncode=0,stdout=json.dumps(report()),stderr="")
            with mock.patch.object(guard.subprocess,"run",return_value=proc) as run:
                svc._native_proxy_log_worker()
                self.assertEqual(run.call_args.kwargs["timeout"],2.5)
                self.assertNotIn("shadowrocket://",str(run.call_args))
            svc.write_status([guard.ProbeResult("edge",True,200,False,.2)],0,True)
            v=json.loads((Path(d)/"status.json").read_text())
            self.assertTrue(v["openai_group_backend_verified"])
            self.assertEqual(v["openai_group_backend_name"],"🇺🇸 USA Seattle 05")
            self.assertEqual(v["openai_group_backend_source"],"shadowrocket_native_proxy_log")
            with mock.patch("time.time",return_value=now+2000):
                svc.write_status([guard.ProbeResult("edge",True,200,False,.2)],0,True)
                v=json.loads((Path(d)/"status.json").read_text())
                self.assertEqual(v["openai_group_backend_name"],"")
                self.assertFalse(v["openai_group_backend_verified"])
                self.assertEqual(v["native_proxy_last_connection"]["name"],"🇺🇸 USA Seattle 05")

    def test_verified_change_history_never_switches_proxy(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.guardian(d)
            now=int(time.time())
            def insert(name,dt):
                entry={"source":"shadowrocket_native_proxy_log","group":"OpenAI-Resilience",
                       "latest":{"source":"shadowrocket_native_proxy_log","group":"OpenAI-Resilience",
                                 "name":name,"host":"chatgpt.com","observed_at":"2026-10-23T19:16:40+08:00","epoch":now+dt}}
                with mock.patch.object(guard.subprocess,"run",return_value=mock.Mock(returncode=0,stdout=json.dumps(entry))):
                    svc._native_proxy_log_worker()
            with mock.patch.object(svc,"attempt_failover") as switch:
                insert("🇺🇸 USA Seattle 05",0)
                insert("🇯🇵 Japan 14",30)
                insert("🇯🇵 Japan 14",30)
                self.assertEqual(len(svc.native_log_history),1)
                event=svc.native_log_history[0]
                self.assertFalse(event["is_fallback_switch_confirmed"])
                switch.assert_not_called()

    def test_disabled_reader_does_not_start_or_read(self):
        with tempfile.TemporaryDirectory() as d:
            svc=self.guardian(d,enabled=False)
            with mock.patch.object(guard.threading,"Thread") as task:
                svc.maybe_begin_native_proxy_log()
                task.assert_not_called()
