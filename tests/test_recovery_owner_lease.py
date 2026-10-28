"""P0 verified crash-only reconnect and P1 no vendor-private reads."""
import logging
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import openai_link_guardian as g


def route(owner, port=1082):
    return {"source":"macos_system_proxy", "state":"explicit",
            "proxy_url":f"http://127.0.0.1:{port}",
            "endpoint":f"127.0.0.1:{port}", "listener_owner":owner}


class RecoveryOwnershipTests(unittest.TestCase):
    def service(self, tmp):
        cfg=dict(g.DEFAULTS)
        cfg.update(proxy_backend_auto_detect_enabled=True,
                   tunnel_recovery_enabled=True,
                   proxy="http://127.0.0.1:1082",
                   automatic_control_enabled=False)
        return g.Guardian(cfg, logging.getLogger("p0-p1"), Path(tmp)/"status.json")

    def owned_then_missing(self, svc):
        with mock.patch.object(svc,"_inspect_system_route",return_value=route("shadowrocket")):
            svc.refresh_active_backend()
        self.assertEqual(svc.active_backend,"shadowrocket")
        with mock.patch.object(svc,"_inspect_system_route",return_value=route("missing")):
            svc.refresh_active_backend()
        self.assertEqual(svc.active_backend,"shadowrocket_recovery_candidate")

    def test_recent_verified_owner_and_os_plugin_failure_reconnects_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp)
            self.owned_then_missing(s)
            good=g.ProbeResult("edge",True,200,False,0.1)
            with mock.patch.object(s,"_inspect_system_route",
                                   side_effect=[route("missing"),route("shadowrocket")]), \
                 mock.patch.object(g,"latest_shadowrocket_stop_reason",return_value="failed"), \
                 mock.patch.object(g,"shadowrocket_app_still_running",return_value=True), \
                 mock.patch.object(s,"recover_missing_tunnel",return_value=(True,[good])) as reconnect, \
                 mock.patch.object(s,"write_status"),mock.patch.object(s,"observe_edge_incident"):
                self.assertTrue(s.recover_verified_missing_shadowrocket())
            reconnect.assert_called_once()
            self.assertEqual(s.active_backend,"shadowrocket")

    def test_manual_or_unknown_stop_never_reconnects(self):
        for reason in ("manual","unknown"):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as tmp:
                s=self.service(tmp)
                self.owned_then_missing(s)
                with mock.patch.object(s,"_inspect_system_route",return_value=route("missing")), \
                     mock.patch.object(g,"latest_shadowrocket_stop_reason",return_value=reason), \
                     mock.patch.object(g,"shadowrocket_app_still_running",return_value=True), \
                     mock.patch.object(s,"recover_missing_tunnel") as reconnect:
                    self.assertFalse(s.recover_verified_missing_shadowrocket())
                reconnect.assert_not_called()
                self.assertEqual(s.recovery_state,"recovery_not_authorized")

    def test_app_closed_never_restarts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp);self.owned_then_missing(s)
            with mock.patch.object(s,"_inspect_system_route",return_value=route("missing")), \
                 mock.patch.object(g,"latest_shadowrocket_stop_reason",return_value="failed"), \
                 mock.patch.object(g,"shadowrocket_app_still_running",return_value=False), \
                 mock.patch.object(s,"recover_missing_tunnel") as reconnect:
                self.assertFalse(s.recover_verified_missing_shadowrocket())
            reconnect.assert_not_called()

    def test_reassigned_or_listening_port_revokes_lease_and_prevents_action(self):
        for observed in (route("other"),route("shadowrocket",7890),route("unverified")):
            with self.subTest(observed=observed),tempfile.TemporaryDirectory() as tmp:
                s=self.service(tmp);self.owned_then_missing(s)
                with mock.patch.object(s,"_inspect_system_route",return_value=observed), \
                     mock.patch.object(s,"recover_missing_tunnel") as reconnect, \
                     mock.patch.object(g,"latest_shadowrocket_stop_reason") as stop:
                    self.assertFalse(s.recover_verified_missing_shadowrocket())
                reconnect.assert_not_called()
                stop.assert_not_called()

    def test_no_historical_owner_or_expired_owner_never_reconnects(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp)
            with mock.patch.object(s,"_inspect_system_route",return_value=route("missing")), \
                 mock.patch.object(s,"_inspect_mihomo",return_value={}):
                s.refresh_active_backend()
            self.assertEqual(s.active_backend,"system_proxy")
            self.owned_then_missing(s)
            s.verified_shadowrocket_at-=120
            with mock.patch.object(s,"recover_missing_tunnel") as reconnect:
                self.assertFalse(s.recover_verified_missing_shadowrocket())
            reconnect.assert_not_called()

    def test_claim_consumed_even_if_reconnect_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp);self.owned_then_missing(s)
            with mock.patch.object(s,"_inspect_system_route",
                                   side_effect=[route("missing"),route("missing")]), \
                 mock.patch.object(g,"latest_shadowrocket_stop_reason",return_value="failed"), \
                 mock.patch.object(g,"shadowrocket_app_still_running",return_value=True), \
                 mock.patch.object(s,"recover_missing_tunnel",return_value=(False,[])) as reconnect, \
                 mock.patch.object(s,"write_status"),mock.patch.object(s,"observe_edge_incident"), \
                 mock.patch.object(s,"_inspect_mihomo",return_value={}):
                self.assertFalse(s.recover_verified_missing_shadowrocket())
            reconnect.assert_called_once()
            self.assertTrue(s.missing_tunnel_reconnect_used)

    def test_shadowrocket_pref_never_queried_in_guardian_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp)
            good=g.ProbeResult("edge",True,200,False,0.1)
            with mock.patch.object(s,"_inspect_system_route",return_value=route("shadowrocket")), \
                 mock.patch.object(g,"current_shadowrocket_node",
                                   side_effect=AssertionError("private read")), \
                 mock.patch.object(g,"proxy_endpoint_available",return_value=True), \
                 mock.patch.object(s,"probe_all",return_value=[good]):
                self.assertTrue(s.cycle())
            self.assertFalse(s.current_node_verified)


if __name__=="__main__":
    unittest.main()
