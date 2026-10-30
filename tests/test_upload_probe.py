"""Uplink throughput probe: trustworthy numbers only, and off by default."""
import importlib.util
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import openai_link_guardian as guardian

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

SPEC = importlib.util.spec_from_file_location(
    "upload_probe", Path(__file__).resolve().parents[1] / "scripts/upload_probe.py")
probe_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_mod)


class UploadProbeTests(unittest.TestCase):
    def _run(self, stdout, returncode=0):
        return mock.patch.object(probe_mod.subprocess, "run",
                                 return_value=mock.Mock(returncode=returncode,
                                                        stdout=stdout, stderr=""))

    def test_full_body_gives_real_rate(self):
        # 1 MiB in 20 s -> 51.2 KB/s
        with self._run("200 1048576 20.0"):
            out = probe_mod.probe("http://127.0.0.1:1082")
        self.assertEqual(out["state"], "ok")
        self.assertEqual(out["bytes"], 1048576)
        self.assertAlmostEqual(out["kbps"], 51.2, places=1)
        self.assertEqual(out["source"], "bounded_upload_probe")

    def test_partial_upload_is_not_reported_as_ok(self):
        # Server answered before the whole body arrived: the rate would be fake.
        with self._run("400 65536 2.0"):
            out = probe_mod.probe("http://127.0.0.1:1082")
        self.assertEqual(out["state"], "partial")

    def test_curl_failure_is_unavailable_not_zero_speed(self):
        with mock.patch.object(probe_mod.subprocess, "run", side_effect=OSError("boom")):
            out = probe_mod.probe("http://127.0.0.1:1082")
        self.assertEqual(out["state"], "unavailable")
        self.assertEqual(out["kbps"], 0.0)

    def test_probe_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            config = dict(guardian.DEFAULTS)
            self.assertFalse(config.get("upload_probe_enabled", False))
            svc = guardian.Guardian(config, logging.getLogger("upload-probe-unit"),
                                    Path(d) / "status.json")
            with mock.patch.object(guardian.threading, "Thread") as t:
                svc.maybe_begin_upload_probe()
                t.assert_not_called()

    def test_enabled_probe_is_throttled_and_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            config = dict(guardian.DEFAULTS, upload_probe_enabled=True, proxy="http://127.0.0.1:1082")
            svc = guardian.Guardian(config, logging.getLogger("upload-probe-unit2"),
                                    Path(d) / "status.json")
            with mock.patch.object(guardian.threading, "Thread") as t:
                svc.maybe_begin_upload_probe()
                svc.maybe_begin_upload_probe()
                self.assertEqual(t.call_count, 1)


class UploadHistoryTests(unittest.TestCase):
    def test_samples_dedupe_per_exit_and_keep_best(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            guardian.record_upload_sample("1.1.1.1", "JP", "NRT", 40.0, 1000, path=path, now=1001)
            entries = guardian.record_upload_sample("1.1.1.1", "JP", "NRT", 150.0, 1010, path=path, now=1011)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["samples"], 2)
            self.assertEqual(entries[0]["best_kbps"], 150.0)
            self.assertEqual(entries[0]["kbps"], 150.0)

    def test_recommends_a_measurably_faster_exit_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            guardian.record_upload_sample("1.1.1.1", "US", "SEA", 40.0, 1000, path=path, now=1001)
            guardian.record_upload_sample("2.2.2.2", "JP", "NRT", 150.0, 1000, path=path, now=1001)
            entries = guardian._load_upload_history(path)

            class Obs:
                egress_ip = "1.1.1.1"
            advice = guardian.upload_recommendation(entries, {"kbps": 40.0}, Obs())
            self.assertEqual(advice["state"], "switch_recommended")
            self.assertEqual(advice["ip"], "2.2.2.2")
            self.assertEqual(advice["best_kbps"], 150.0)
            self.assertEqual(advice["identity"], "exit_ip_not_subscription_name")

            class Same(Obs):
                egress_ip = "2.2.2.2"
            self.assertEqual(
                guardian.upload_recommendation(entries, {"kbps": 150.0}, Same())["state"],
                "no_advice")

    def test_stale_history_expires(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            guardian.record_upload_sample("1.1.1.1", "US", "SEA", 40.0, 1000, path=path, now=1001)
            entries = guardian.record_upload_sample(
                "2.2.2.2", "JP", "NRT", 150.0, 900000, path=path, now=900001, max_age=3600)
            self.assertEqual([e["ip"] for e in entries], ["2.2.2.2"])


    def test_same_measurement_is_not_counted_twice(self):
        """Status is written every ~10s; one probe must count as one sample."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "history.json"
            guardian.record_upload_sample("1.1.1.1", "JP", "NRT", 40.0, 1000, path=path, now=1001)
            for tick in range(1002, 1009):
                entries = guardian.record_upload_sample(
                    "1.1.1.1", "JP", "NRT", 40.0, 1000, path=path, now=tick)
            self.assertEqual(entries[0]["samples"], 1)

    def test_manual_request_file_forces_an_immediate_probe(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            config = dict(guardian.DEFAULTS, upload_probe_enabled=True,
                          proxy="http://127.0.0.1:1082")
            svc = guardian.Guardian(config, logging.getLogger("upload-probe-unit3"),
                                    home / "status.json")
            svc.upload_probe_last_run = guardian.time.monotonic()  # just measured
            with mock.patch.object(guardian, "DEFAULT_HOME", home):
                with mock.patch.object(guardian.threading, "Thread") as t:
                    svc.maybe_begin_upload_probe()      # throttled, no request file
                    self.assertEqual(t.call_count, 0)
                svc.upload_probe_running = False
                (home / "upload_probe.request").write_text("x")
                with mock.patch.object(guardian.threading, "Thread") as t2:
                    svc.maybe_begin_upload_probe()      # forced
                    self.assertEqual(t2.call_count, 1)
                self.assertFalse((home / "upload_probe.request").exists())


if __name__ == "__main__":
    unittest.main()
