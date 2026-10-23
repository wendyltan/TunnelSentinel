import json
import logging
import tempfile
import time
from pathlib import Path
from unittest import TestCase, mock

import openai_link_guardian as guardian


class AIMatrixTests(TestCase):
    def new_service(self, root):
        cfg = dict(guardian.DEFAULTS)
        cfg["ai_matrix_enabled"] = True
        cfg["ai_matrix_interval_seconds"] = 900
        logger = logging.getLogger("ai-matrix-test")
        logger.addHandler(logging.NullHandler())
        with mock.patch.object(guardian, "current_shadowrocket_node", return_value="Japan 04"):
            service = guardian.Guardian(cfg, logger, Path(root) / "status.json")
        return service

    def test_targets_match_website_public_trace_method_without_external_js(self):
        domains = [domain for _, domain in guardian.AI_TRACE_TARGETS]
        self.assertEqual(len(domains), len(set(domains)))
        self.assertIn("chatgpt.com", domains)
        self.assertIn("openai.com", domains)
        self.assertIn("www.perplexity.ai", domains)
        self.assertNotIn("nxonearth.com", domains)

    def test_audit_preserves_per_site_exit_and_has_no_node_name(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            def fake_probe(name, url, proxy):
                self.assertEqual(proxy, service.config["proxy"])
                self.assertTrue(url.endswith("/cdn-cgi/trace"))
                is_openai = "chatgpt.com" in url or "openai.com" in url
                return guardian.ProbeResult(
                    name, True, 200, False, .2, "",
                    "1.2.3.4" if is_openai else "5.6.7.8",
                    "SEA" if is_openai else "NRT",
                    "US" if is_openai else "JP")
            with mock.patch.object(guardian, "curl_probe", side_effect=fake_probe):
                service._ai_matrix_runner()
            good = guardian.ProbeResult("edge", True, 200, False, .1, "",
                                        "1.2.3.4", "SEA", "US")
            service.write_status([good], 0, True)
            status = json.loads((Path(root) / "status.json").read_text())
            self.assertTrue(status["ai_matrix_fresh"])
            self.assertEqual(len(status["ai_matrix_sites"]), len(guardian.AI_TRACE_TARGETS))
            by_name = {row["name"]:row for row in status["ai_matrix_sites"]}
            self.assertEqual(by_name["ChatGPT"]["egress_colo"], "SEA")
            self.assertEqual(by_name["Claude"]["egress_colo"], "NRT")
            self.assertEqual(status["openai_group_backend_name"], "")
            self.assertFalse(status["openai_group_backend_verified"])

    def test_failed_probe_is_unverified_not_unsupported(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            with mock.patch.object(guardian, "curl_probe", return_value=guardian.ProbeResult(
                "ai-openai.com", False, 403, False, 4, "TLS error")):
                service._ai_matrix_runner()
            for check in service.ai_matrix_checks:
                self.assertEqual(check["status"], "unverified")
                self.assertEqual(check["egress_ip"], "")
            self.assertEqual(service.recovery_state, "monitoring")

    def test_results_expire_after_interval_or_network_fault(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            service.ai_matrix_checks = [{"name":"OpenAI","domain":"openai.com","status":"reachable"}]
            service.ai_matrix_checked_at = time.time()-1900
            good = guardian.ProbeResult("edge", True, 200, False, .1)
            service.write_status([good], 0, True)
            state = json.loads((Path(root) / "status.json").read_text())
            self.assertFalse(state["ai_matrix_fresh"])
            self.assertEqual(state["ai_matrix_sites"], [])
            service.ai_matrix_checked_at = time.time()
            service.write_status([good], 0, False)
            state = json.loads((Path(root) / "status.json").read_text())
            self.assertEqual(state["ai_matrix_sites"], [])
            self.assertFalse(state["ai_matrix_fresh"])

    def test_method_audit_marks_only_observed_head_challenge_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            service.config["endpoint_method_audit_enabled"] = True
            def fake_probe(name, url, proxy, **options):
                if options.get("http_head"):
                    self.assertEqual(name, "method-head-current-route")
                    return guardian.ProbeResult(name, False, 403, True, .2)
                return guardian.ProbeResult(name, True, 200, False, .1, "",
                                            "1.2.3.4", "SEA", "US")
            with mock.patch.object(guardian, "curl_probe", side_effect=fake_probe) as probe:
                service._ai_matrix_runner()
            head_calls = [call for call in probe.call_args_list
                          if call.kwargs.get("http_head")]
            self.assertEqual(len(head_calls), 1)
            service.write_status([guardian.ProbeResult("edge", True, 200, False, .2)],0,True)
            state = json.loads((Path(root)/"status.json").read_text())
            audit = state["endpoint_method_audit"]
            self.assertEqual(audit["get_code"], 200)
            self.assertEqual(audit["head_code"], 403)
            self.assertEqual(audit["result"], "possible_head_false_negative")
            self.assertEqual(audit["scope"], "current_route_only_not_native_fallback_proof")
            self.assertEqual(service.recovery_state, "monitoring")

    def test_method_audit_does_not_report_native_group_method_or_trigger_switch(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            service.config["endpoint_method_audit_enabled"] = True
            def fake_probe(name, url, proxy, **options):
                if options.get("http_head"):
                    return guardian.ProbeResult(name, True, 200, False, .25)
                return guardian.ProbeResult(name, True, 200, False, .3, "",
                                            "5.6.7.8","NRT","JP")
            with mock.patch.object(guardian, "curl_probe", side_effect=fake_probe):
                service._ai_matrix_runner()
            service.write_status([guardian.ProbeResult("edge", True, 200, False, .25)],0,True)
            state = json.loads((Path(root)/"status.json").read_text())
            self.assertEqual(state["endpoint_method_audit"]["result"], "no_mismatch_observed")
            self.assertFalse(state["openai_group_backend_verified"])
            service.write_status([guardian.ProbeResult("edge", False, 0, False, 1)],0,False)
            state = json.loads((Path(root)/"status.json").read_text())
            self.assertEqual(state["endpoint_method_audit"], {})

    def test_head_rejected_without_cloudflare_marker_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            service.config["endpoint_method_audit_enabled"] = True
            def fake_probe(name, url, proxy, **options):
                if options.get("http_head"):
                    return guardian.ProbeResult(name, True, 403, False, .25)
                return guardian.ProbeResult(name, True, 200, False, .3, "",
                                            "5.6.7.8","SEA","US")
            with mock.patch.object(guardian, "curl_probe", side_effect=fake_probe):
                service._ai_matrix_runner()
            service.write_status(
                [guardian.ProbeResult("edge", True, 200, False, .3)],
                0, True)
            state = json.loads((Path(root)/"status.json").read_text())
            self.assertEqual(state["endpoint_method_audit"]["result"], "inconclusive")

    def test_method_audit_default_disabled_and_does_not_extra_request(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            self.assertFalse(service.config.get("endpoint_method_audit_enabled"))
            ok = guardian.ProbeResult("ai-foo", True, 200, False, .2, "",
                                       "5.6.7.8","NRT","JP")
            with mock.patch.object(guardian, "curl_probe", return_value=ok) as probe:
                service._ai_matrix_runner()
            self.assertEqual(probe.call_count, len(guardian.AI_TRACE_TARGETS))
            service.write_status([guardian.ProbeResult("edge", True, 200, False, .2)],0,True)
            state = json.loads((Path(root)/"status.json").read_text())
            self.assertEqual(state["endpoint_method_audit"], {})

    def test_throttled_background_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            service = self.new_service(root)
            with mock.patch.object(guardian.threading, "Thread") as worker:
                service.maybe_begin_ai_matrix(False)
                worker.assert_not_called()
                service.maybe_begin_ai_matrix(True)
                self.assertEqual(worker.call_count, 1)
                service.maybe_begin_ai_matrix(True)
                self.assertEqual(worker.call_count, 1)
                self.assertTrue(service.ai_matrix_running)
