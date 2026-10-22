import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import openai_link_guardian as guardian


class GuardianTests(unittest.TestCase):
    def test_cloudflare_challenge_detection(self):
        self.assertTrue(guardian.is_cloudflare_challenge("cf-mitigated: challenge", ""))
        self.assertTrue(guardian.is_cloudflare_challenge("", "Enable JavaScript and cookies to continue"))
        self.assertFalse(guardian.is_cloudflare_challenge("content-type: application/json", "{}"))

    def test_real_desktop_errors_are_classified_without_failover(self):
        cases = {
            "cloudflare_challenge": "cloudflare",
            'Thread catalog sync failed errorMessage="Authenticated desktop fetch failed (429)"': "rate_limit",
            'sa_server_request_failed errorMessage="Too many requests"': "rate_limit",
            "sa_server_request_failed net::ERR_CONNECTION_CLOSED": "connection",
            "ResizeObserver loop completed with undelivered notifications": "layout",
        }
        for line, category in cases.items():
            with self.subTest(category=category):
                self.assertEqual(guardian.LogWatcher.classify_issue(line), category)
                self.assertFalse(guardian.LogWatcher._is_actionable(line))

    def test_real_error_events_surface_in_status_without_proxy_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            log_dir = path / "logs" / "2026" / "10" / "22"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text("baseline\n", encoding="utf-8")
            watcher = guardian.LogWatcher(path / "logs")
            self.assertEqual(watcher.read_new_failures(), [])
            with log_file.open("a", encoding="utf-8") as out:
                out.write("sa_server_request_failed errorCode=cloudflare_challenge\n")
                out.write('Authenticated desktop fetch failed (429)\n')
                out.write("ResizeObserver loop completed with undelivered notifications\n" * 3)
            self.assertEqual(watcher.read_new_failures(), [])
            categories = {issue["category"] for issue in watcher.issue_summary()}
            self.assertEqual(categories, {"cloudflare", "rate_limit", "layout"})
            config = dict(guardian.DEFAULTS)
            logger = logging.getLogger("issue-status-test")
            logger.addHandler(logging.NullHandler())
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="node"):
                service = guardian.Guardian(config, logger, path / "status.json")
            service.log_watcher = watcher
            good = guardian.ProbeResult("edge", True, 200, False, .3)
            with mock.patch.object(guardian, "proxy_endpoint_available", return_value=True):
                with mock.patch.object(service, "probe_all", return_value=[good]):
                    with mock.patch.object(service, "attempt_failover") as failover:
                        self.assertTrue(service.cycle())
            failover.assert_not_called()
            status = guardian.json.loads((path / "status.json").read_text())
            self.assertTrue(status["healthy"])
            self.assertEqual(status["overall_status"], "attention")
            self.assertEqual(status["business_status"], "attention")
            self.assertEqual(len(status["business_issues"]), 3)
            self.assertGreater(status["pid"], 1)

    def test_recent_warning_survives_guardian_restart_without_auto_switch(self):
        from datetime import datetime, timezone, timedelta
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "2026" / "10" / "22"
            folder.mkdir(parents=True)
            stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            stale = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(
                timespec="milliseconds").replace("+00:00", "Z")
            (folder / "app.log").write_text(
                f'{stale} warning errorCode=cloudflare_challenge\n'
                f'{stamp} warning errorCode=cloudflare_challenge\n'
                f'{stamp} warning errorMessage="Too many requests"\n'
                f'{stamp} warning ERR_TUNNEL_CONNECTION_FAILED\n',
                encoding="utf-8",
            )
            watcher = guardian.LogWatcher(root)
            self.assertEqual(watcher.read_new_failures(), [])
            categories = {issue["category"] for issue in watcher.issue_summary()}
            self.assertEqual(categories, {"cloudflare", "rate_limit"})

    def test_old_business_errors_expire_without_corrupting_proxy_health(self):
        watcher = guardian.LogWatcher(Path("/nonexistent"))
        now = guardian.time.time()
        watcher.issue_events.append((now - guardian.ISSUE_WINDOW_SECONDS - 1, "cloudflare"))
        watcher.issue_events.append((now, "rate_limit"))
        watcher.issue_events.append((now, "layout"))
        self.assertEqual([item["category"] for item in watcher.issue_summary()], ["rate_limit"])
        watcher.issue_events.append((now, "layout"))
        watcher.issue_events.append((now, "layout"))
        self.assertEqual({item["category"] for item in watcher.issue_summary()},
                         {"rate_limit", "layout"})

    def test_status_distinguishes_failed_edge_from_business_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dict(guardian.DEFAULTS)
            logger = logging.getLogger("edge-separation-test")
            logger.addHandler(logging.NullHandler())
            service = guardian.Guardian(config, logger, Path(tmp) / "status.json")
            service.log_watcher.issue_events.append((guardian.time.time(), "rate_limit"))
            service.write_status([guardian.ProbeResult("edge", False, 0, False, 1.0)],
                                 0, False, proxy_available=True)
            status = guardian.json.loads((Path(tmp) / "status.json").read_text())
            self.assertEqual(status["overall_status"], "offline")
            self.assertEqual(status["business_status"], "attention")

    def test_candidate_rotation_starts_after_current(self):
        nodes = ["a", "b", "c"]
        self.assertEqual(guardian.ordered_candidates(nodes, "b"), ["c", "a", "b"])
        self.assertEqual(guardian.ordered_candidates(nodes, "missing"), nodes)

    def test_url_scheme_timeout_is_left_to_network_verification(self):
        with mock.patch.object(
            guardian.subprocess,
            "run",
            side_effect=guardian.subprocess.TimeoutExpired(cmd="open", timeout=3),
        ):
            self.assertTrue(guardian.select_shadowrocket_node("node", False))

    def test_connect_url_scheme_timeout_is_left_to_listener_verification(self):
        with mock.patch.object(
            guardian.subprocess,
            "run",
            side_effect=guardian.subprocess.TimeoutExpired(cmd="open", timeout=3),
        ):
            self.assertTrue(guardian.connect_shadowrocket_tunnel(False))

    def test_node_preference_falls_back_to_saved_plist_if_export_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            domain = Path(tmp) / "group.com.liguangming.Shadowrocket"
            Path(str(domain) + ".plist").write_bytes(
                guardian.plistlib.dumps({guardian.SHADOWROCKET_NODE_KEY: "Japan 14"})
            )
            with mock.patch.object(guardian, "SHADOWROCKET_PREF_DOMAIN", domain):
                with mock.patch.object(
                    guardian.subprocess, "run", side_effect=[
                        mock.Mock(returncode=1),
                        mock.Mock(returncode=0, stdout=domain.with_name(domain.name + ".plist").read_bytes()),
                    ]
                ) as run:
                    self.assertEqual(guardian.current_shadowrocket_node(), "Japan 14")
                    self.assertEqual(run.call_count, 2)

    def test_node_preference_read_is_bounded_when_os_blocks_it(self):
        with mock.patch.object(
            guardian.subprocess, "run",
            side_effect=guardian.subprocess.TimeoutExpired(cmd="defaults", timeout=1),
        ):
            self.assertIsNone(guardian.current_shadowrocket_node())

    def test_latest_tunnel_stop_reason_distinguishes_manual_and_failure(self):
        manual = mock.Mock(
            returncode=0,
            stdout="status changed to disconnected, last stop reason Stop command received\n",
        )
        with mock.patch.object(guardian.subprocess, "run", return_value=manual):
            self.assertEqual(guardian.latest_shadowrocket_stop_reason(300), "manual")
        failed = mock.Mock(
            returncode=0,
            stdout="status changed to disconnected, last stop reason Plugin failed\n",
        )
        with mock.patch.object(guardian.subprocess, "run", return_value=failed):
            self.assertEqual(guardian.latest_shadowrocket_stop_reason(300), "failed")

    def test_log_watcher_ignores_history_then_reads_new_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "2026" / "09" / "06"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text("ERR_TUNNEL_CONNECTION_FAILED old\n", encoding="utf-8")
            watcher = guardian.LogWatcher(root)
            self.assertEqual(watcher.read_new_failures(), [])
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write("ERR_TUNNEL_CONNECTION_FAILED new\n")
            self.assertEqual(len(watcher.read_new_failures()), 1)

    def test_log_watcher_restores_existing_pubsub_outage_without_counting_old_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "2026" / "10" / "05"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text(
                "ERR_TUNNEL_CONNECTION_FAILED old\n"
                "chatgpt_pubsub_transport_closed windowFocused=true rendererWebContentsId=1\n",
                encoding="utf-8",
            )
            watcher = guardian.LogWatcher(root)
            self.assertEqual(watcher.read_new_failures(), [])
            watcher.pubsub_closed_at["1"] -= guardian.PUBSUB_OUTAGE_SECONDS
            self.assertEqual(len(watcher.read_new_failures()), 1)

    def test_log_watcher_detects_current_proxy_failure_marker(self):
        line = "chatgpt_pubsub_connection_failed error=net::ERR_PROXY_CONNECTION_FAILED"
        self.assertTrue(guardian.LogWatcher._is_actionable(line))

    def test_log_watcher_ignores_transient_pubsub_reconnect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "2026" / "10" / "05"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text("healthy\n", encoding="utf-8")
            watcher = guardian.LogWatcher(root)
            watcher.read_new_failures()
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write("chatgpt_pubsub_transport_closed windowFocused=true\n")
                handle.write("chatgpt_pubsub_transport_opened windowFocused=true\n")
            self.assertEqual(watcher.read_new_failures(), [])

    def test_log_watcher_reports_pubsub_outage_after_grace_period(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "2026" / "10" / "05"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text("healthy\n", encoding="utf-8")
            watcher = guardian.LogWatcher(root)
            watcher.read_new_failures()
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write("chatgpt_pubsub_transport_closed windowFocused=true\n")
            self.assertEqual(watcher.read_new_failures(), [])
            first_close = watcher.pubsub_closed_at["primary"]
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write("chatgpt_pubsub_transport_closed windowFocused=true\n")
            self.assertEqual(watcher.read_new_failures(), [])
            self.assertEqual(watcher.pubsub_closed_at["primary"], first_close)
            watcher.pubsub_closed_at["primary"] -= guardian.PUBSUB_OUTAGE_SECONDS
            self.assertEqual(len(watcher.read_new_failures()), 1)
            self.assertEqual(watcher.read_new_failures(), [])
            watcher.pubsub_last_failure_at["primary"] -= guardian.PUBSUB_FAILURE_REPEAT_SECONDS
            self.assertEqual(len(watcher.read_new_failures()), 1)

    def test_log_watcher_matches_pubsub_reopen_to_renderer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "2026" / "10" / "05"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "desktop.log"
            log_file.write_text("healthy\n", encoding="utf-8")
            watcher = guardian.LogWatcher(root)
            watcher.read_new_failures()
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(
                    "chatgpt_pubsub_transport_closed windowFocused=true rendererWebContentsId=1\n"
                )
                handle.write(
                    "chatgpt_pubsub_transport_opened windowFocused=false rendererWebContentsId=3\n"
                )
            self.assertEqual(watcher.read_new_failures(), [])
            watcher.pubsub_closed_at["1"] -= guardian.PUBSUB_OUTAGE_SECONDS
            self.assertEqual(len(watcher.read_new_failures()), 1)

    def test_known_good_cache_expires_without_restarting_daemon(self):
        cfg = dict(guardian.DEFAULTS)
        logger = logging.getLogger("candidate-expiry-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            svc = guardian.Guardian(cfg, logger, Path(tmp) / "status.json")
            svc.learned_good_nodes = ["previously-good"]
            svc.known_good_cache_updated_at -= 301
            with mock.patch.object(guardian, "read_known_good_nodes", return_value=[]):
                self.assertEqual(svc.known_good_candidates(), [])

    def test_stale_config_nodes_are_not_used_for_rotation(self):
        config = dict(guardian.DEFAULTS)
        config["nodes"] = ["old-node-A", "old-node-B"]
        config["dry_run"] = False
        logger = logging.getLogger("stale-config-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="offline"):
                svc = guardian.Guardian(config, logger, Path(tmp) / "status.json")
            svc.learned_good_nodes = ["Japan 14"]
            with mock.patch.object(guardian, "select_shadowrocket_node", return_value=True) as select:
                with mock.patch.object(guardian, "wait_for_shadowrocket_node", return_value=False) as verify:
                    self.assertFalse(svc.attempt_failover())
            select.assert_called_once_with("Japan 14", False)
            verify.assert_called_once()
            self.assertEqual(svc.recovery_state, "selector_unavailable")
            self.assertGreater(svc.recovery_retry_at, guardian.time.monotonic())

    def test_no_verified_candidate_does_not_request_any_switch(self):
        config = dict(guardian.DEFAULTS)
        config["nodes"] = ["stale-1", "stale-2"]
        logger = logging.getLogger("no-candidate-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            svc = guardian.Guardian(config, logger, Path(tmp) / "status.json")
            svc.learned_good_nodes = []
            with mock.patch.object(guardian, "select_shadowrocket_node") as select:
                self.assertFalse(svc.attempt_failover())
            select.assert_not_called()
            self.assertEqual(svc.recovery_state, "no_candidates")

    def test_healthy_probe_ignores_log_errors_for_failover(self):
        cfg = dict(guardian.DEFAULTS)
        logger = logging.getLogger("healthy-log-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="Japan 14"):
                svc = guardian.Guardian(cfg, logger, Path(tmp) / "status.json")
                svc.failure_times.extend([guardian.time.monotonic()] * 4)
                good = guardian.ProbeResult("edge", True, 200, False, .2)
                with mock.patch.object(guardian, "proxy_endpoint_available", return_value=True), \
                     mock.patch.object(svc, "probe_all", return_value=[good]), \
                     mock.patch.object(svc.log_watcher, "read_new_failures", return_value=["ERR_TUNNEL_CONNECTION_FAILED"]), \
                     mock.patch.object(svc, "attempt_failover") as switch:
                    self.assertTrue(svc.cycle())
            switch.assert_not_called()
            self.assertEqual(len(svc.failure_times), 0)

    def test_native_fallback_never_calls_broken_external_selector(self):
        cfg = dict(guardian.DEFAULTS)
        cfg["startup_grace_seconds"] = 0
        cfg["native_fallback_enabled"] = True
        cfg["native_fallback_group"] = "OpenAI-Resilience"
        logger = logging.getLogger("native-fallback-owner-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            svc = guardian.Guardian(cfg, logger, Path(tmp) / "status.json")
            svc.failure_times.extend([guardian.time.monotonic()] * 5)
            with mock.patch.object(svc, "attempt_failover") as rotate:
                self.assertFalse(svc.should_switch())
                rotate.assert_not_called()
            self.assertEqual(svc.recovery_state, "native_fallback_waiting")
            svc.write_status([guardian.ProbeResult("edge", False, 0, False, 1.0)], 0, False)
            status = guardian.json.loads((Path(tmp) / "status.json").read_text())
            self.assertEqual(status["route_management"], "native_fallback")
            self.assertEqual(status["native_fallback_group"], "OpenAI-Resilience")
            self.assertEqual(status["current_node_scope"], "shadowrocket_global_selection")

    def test_unverified_current_node_blocks_automatic_switch(self):
        cfg = dict(guardian.DEFAULTS)
        cfg["startup_grace_seconds"] = 0
        logger = logging.getLogger("unverified-control-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            svc = guardian.Guardian(cfg, logger, Path(tmp) / "status.json")
            svc.current_node_verified = False
            svc.failure_times.extend([guardian.time.monotonic()] * 5)
            self.assertFalse(svc.should_switch())
            self.assertEqual(svc.recovery_state, "node_unverified")

    def test_manual_node_change_suppresses_churn(self):
        cfg = dict(guardian.DEFAULTS)
        cfg["startup_grace_seconds"] = 0
        logger = logging.getLogger("manual-change-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="old"):
                svc = guardian.Guardian(cfg, logger, Path(tmp) / "status.json")
            svc.failure_times.extend([guardian.time.monotonic()] * 4)
            bad = guardian.ProbeResult("edge", False, 0, False, 1.0)
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="user-new"), \
                 mock.patch.object(guardian, "proxy_endpoint_available", return_value=True), \
                 mock.patch.object(svc, "probe_all", return_value=[bad]), \
                 mock.patch.object(svc, "attempt_failover") as switch:
                self.assertFalse(svc.cycle())
            switch.assert_not_called()
            self.assertGreater(svc.manual_override_until, guardian.time.monotonic())
            self.assertEqual(svc.current_node, "user-new")

    def test_recovery_status_exposes_failed_control_channel(self):
        cfg = dict(guardian.DEFAULTS)
        logger = logging.getLogger("status-recovery-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            svc = guardian.Guardian(cfg, logger, path)
            svc.learned_good_nodes = ["known"]
            svc.recovery_state = "selector_unavailable"
            svc.recovery_reason = "指令已发送，但未切换"
            svc.recovery_retry_at = guardian.time.monotonic()+600
            svc.write_status([guardian.ProbeResult("edge",False,0,False,0.5)],0,False)
            status = guardian.json.loads(path.read_text())
            self.assertEqual(status["recovery_state"],"selector_unavailable")
            self.assertGreater(status["recovery_retry_seconds"],590)
            self.assertEqual(status["known_good_candidates"],["known"])

    def test_health_uses_public_edge_without_misreading_unauthorized_challenge(self):
        ok = guardian.ProbeResult("edge", True, 200, False, 0.1)
        self.assertTrue(guardian.Guardian.path_is_healthy([ok]))
        bad_edge = guardian.ProbeResult("edge", False, 0, False, 0.1)
        self.assertFalse(guardian.Guardian.path_is_healthy([bad_edge]))

    def test_new_rotated_log_is_read_after_initialization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_dir = root / "2026" / "09" / "06"
            first_dir.mkdir(parents=True)
            (first_dir / "first.log").write_text("healthy\n", encoding="utf-8")
            watcher = guardian.LogWatcher(root)
            watcher.read_new_failures()
            (first_dir / "second.log").write_text(
                "ERR_TUNNEL_CONNECTION_FAILED new file\n", encoding="utf-8"
            )
            self.assertEqual(len(watcher.read_new_failures()), 1)

    def test_failover_selects_next_node_and_verifies_network(self):
        config = dict(guardian.DEFAULTS)
        config.update(
            {
                "nodes": ["a", "b", "c"],
                "initial_node": "a",
                "switch_settle_seconds": 0,
                "dry_run": False,
            }
        )
        logger = logging.getLogger("failover-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value=None):
                service = guardian.Guardian(config, logger, Path(temp_dir) / "status.json")
            service.learned_good_nodes = ["b", "c"]
            good = guardian.ProbeResult("edge", True, 200, False, 0.1)
            with mock.patch.object(guardian, "select_shadowrocket_node", return_value=True) as select:
                with mock.patch.object(guardian, "wait_for_shadowrocket_node", return_value=True):
                    with mock.patch.object(service, "probe_all", return_value=[good]):
                        self.assertTrue(service.attempt_failover())
            select.assert_called_once_with("b", False)
            self.assertEqual(service.current_node, "b")

    def test_failover_rejects_unconfirmed_node_selection(self):
        config = dict(guardian.DEFAULTS)
        config.update({"nodes": ["a"], "initial_node": "a", "dry_run": False})
        logger = logging.getLogger("unconfirmed-node-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as temp_dir:
            service = guardian.Guardian(config, logger, Path(temp_dir) / "status.json")
            with mock.patch.object(guardian, "select_shadowrocket_node", return_value=True):
                with mock.patch.object(guardian, "wait_for_shadowrocket_node", return_value=False):
                    with mock.patch.object(service, "probe_all") as probe:
                        self.assertFalse(service.attempt_failover())
            probe.assert_not_called()

    def test_cycle_syncs_manual_shadowrocket_node(self):
        config = dict(guardian.DEFAULTS)
        logger = logging.getLogger("node-sync-test")
        logger.addHandler(logging.NullHandler())
        good = guardian.ProbeResult("edge", True, 200, False, 0.1)
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value="manual-node"):
                service = guardian.Guardian(config, logger, status_path)
                with mock.patch.object(guardian, "proxy_endpoint_available", return_value=True):
                    with mock.patch.object(service, "probe_all", return_value=[good]):
                        self.assertTrue(service.cycle())
            payload = guardian.json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["current_node"], "manual-node")
            self.assertTrue(payload["current_node_verified"])

    def test_manual_tunnel_stop_suppresses_automatic_recovery(self):
        config = dict(guardian.DEFAULTS)
        logger = logging.getLogger("manual-stop-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            service = guardian.Guardian(config, logger, status_path)
            with mock.patch.object(guardian, "proxy_endpoint_available", return_value=False):
                with mock.patch.object(guardian, "latest_shadowrocket_stop_reason", return_value="manual"):
                    with mock.patch.object(guardian, "connect_shadowrocket_tunnel") as connect:
                        self.assertTrue(service.cycle())
            connect.assert_not_called()
            self.assertTrue(service.manual_pause)
            self.assertEqual(service.failure_times, guardian.collections.deque())
            self.assertEqual(
                guardian.json.loads(status_path.read_text(encoding="utf-8"))["tunnel_state"],
                "manual_pause",
            )

    def test_failed_tunnel_is_reconnected_and_verified(self):
        config = dict(guardian.DEFAULTS)
        config.update(
            {
                "tunnel_reconnect_settle_seconds": 0,
                "tunnel_reconnect_cooldown_seconds": 0,
            }
        )
        logger = logging.getLogger("tunnel-recovery-test")
        logger.addHandler(logging.NullHandler())
        good = guardian.ProbeResult("edge", True, 200, False, 0.1)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = guardian.Guardian(config, logger, Path(temp_dir) / "status.json")
            with mock.patch.object(
                guardian,
                "proxy_endpoint_available",
                side_effect=[False, True, True],
            ):
                with mock.patch.object(
                    guardian, "latest_shadowrocket_stop_reason", return_value="failed"
                ):
                    with mock.patch.object(
                        guardian, "connect_shadowrocket_tunnel", return_value=True
                    ) as connect:
                        with mock.patch.object(service, "probe_all", return_value=[good]):
                            self.assertTrue(service.cycle())
            connect.assert_called_once_with(False)
            self.assertFalse(service.manual_pause)

    def test_manual_pause_is_loaded_and_cleared_when_tunnel_returns(self):
        config = dict(guardian.DEFAULTS)
        logger = logging.getLogger("manual-pause-persistence-test")
        logger.addHandler(logging.NullHandler())
        good = guardian.ProbeResult("edge", True, 200, False, 0.1)
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            status_path.write_text('{"manual_pause": true}', encoding="utf-8")
            service = guardian.Guardian(config, logger, status_path)
            self.assertTrue(service.manual_pause)
            with mock.patch.object(guardian, "proxy_endpoint_available", return_value=True):
                with mock.patch.object(service, "probe_all", return_value=[good]):
                    self.assertTrue(service.cycle())
            self.assertFalse(service.manual_pause)

    def test_current_node_is_restored_from_previous_status(self):
        config = dict(guardian.DEFAULTS)
        config.update({"nodes": ["a", "b"], "initial_node": "a"})
        logger = logging.getLogger("current-node-persistence-test")
        logger.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            status_path.write_text('{"current_node": "b"}', encoding="utf-8")
            with mock.patch.object(guardian, "current_shadowrocket_node", return_value=None):
                service = guardian.Guardian(config, logger, status_path)
            self.assertEqual(service.current_node, "b")


if __name__ == "__main__":
    unittest.main()
