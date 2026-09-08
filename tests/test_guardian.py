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
            service = guardian.Guardian(config, logger, Path(temp_dir) / "status.json")
            good = guardian.ProbeResult("edge", True, 200, False, 0.1)
            with mock.patch.object(guardian, "select_shadowrocket_node", return_value=True) as select:
                with mock.patch.object(service, "probe_all", return_value=[good]):
                    self.assertTrue(service.attempt_failover())
            select.assert_called_once_with("b", False)
            self.assertEqual(service.current_node, "b")

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
            service = guardian.Guardian(config, logger, status_path)
            self.assertEqual(service.current_node, "b")


if __name__ == "__main__":
    unittest.main()
