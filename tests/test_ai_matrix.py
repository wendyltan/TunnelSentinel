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
