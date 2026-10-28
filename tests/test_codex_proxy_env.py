import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_proxy_env import (
    BEGIN, END, UnsafeEnv, managed_url, rollback, state, sync, make_block
)
URL="http://127.0.0.1:1082"
ALT="http://127.0.0.1:7897"


class CodexEnvTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)/".codex"/".env"

    def test_sync_without_existing_env_then_rollback_removes_it(self):
        x=sync(self.p,URL,test_proxy=False)
        self.assertEqual(x["state"],"synced")
        self.assertEqual(state(self.p,URL)["state"],"synced")
        self.assertEqual(self.p.stat().st_mode & 0o777,0o600)
        self.assertEqual(rollback(self.p)["state"],"rolled_back")
        self.assertFalse(self.p.exists())
        self.assertEqual(len(list(self.p.parent.joinpath("proxy-env-backups").glob("*"))),1)

    def test_existing_other_settings_untouched(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text('custom_key="keep-me"\n',encoding="utf-8")
        self.assertEqual(sync(self.p,URL,test_proxy=False)["state"],"synced")
        self.assertIn('custom_key="keep-me"',self.p.read_text())
        self.assertEqual(rollback(self.p)["state"],"rolled_back")
        self.assertEqual(self.p.read_text(),'custom_key="keep-me"\n\n')
        self.assertEqual(len(list(self.p.parent.joinpath("proxy-env-backups").glob("*"))),2)

    def test_old_desktop_script_marker_compatible(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text(make_block(URL))
        self.assertEqual(managed_url(self.p.read_text()),URL)
        self.assertEqual(state(self.p,URL)["state"],"synced")
        self.assertEqual(sync(self.p,URL,test_proxy=False)["state"],"unchanged")
        self.assertEqual(rollback(self.p)["state"],"rolled_back")

    def test_dry_run_never_creates_file(self):
        self.assertEqual(sync(self.p,URL,test_proxy=False,dry_run=True)["state"],"would_sync")
        self.assertFalse(self.p.exists())
        self.p.parent.mkdir(parents=True)
        self.p.write_text(make_block(URL))
        self.assertEqual(rollback(self.p,dry_run=True)["state"],"would_rollback")
        self.assertTrue(self.p.exists())

    def test_unmanaged_proxy_keys_are_preserved_and_refused(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text('MY_VAR=keep\nHTTP_PROXY="http://1.2.3.4:9999"\n')
        original=self.p.read_bytes()
        with self.assertRaises(UnsafeEnv):sync(self.p,URL,test_proxy=False)
        self.assertEqual(self.p.read_bytes(),original)

    def test_symlink_refuses_mutation(self):
        self.p.parent.mkdir(parents=True)
        q=Path(self.temp.name)/"private_env";q.write_text("PRIVATE=keep\n")
        self.p.symlink_to(q)
        with self.assertRaises(UnsafeEnv):sync(self.p,URL,test_proxy=False)
        with self.assertRaises(UnsafeEnv):rollback(self.p)
        self.assertEqual(q.read_text(),"PRIVATE=keep\n")

    def test_duplicate_or_broken_markers_refused(self):
        self.p.parent.mkdir(parents=True)
        for invalid in (BEGIN+"\n",BEGIN+"\n"+END+"\n"+BEGIN+"\n"+END+"\n"):
            self.p.write_text(invalid)
            with self.assertRaises(UnsafeEnv):sync(self.p,URL,test_proxy=False)
            with self.assertRaises(UnsafeEnv):rollback(self.p)
            self.assertEqual(self.p.read_text(),invalid)

    def test_no_arbitrary_proxy_hosts_or_scheme(self):
        for bad in ("http://example.org:1082","socks5://127.0.0.1:1082",
                    "http://127.0.0.1:0","http://127.0.0.1:99999"):
            with self.assertRaises(UnsafeEnv):sync(self.p,bad,test_proxy=False)

    def test_existing_identical_proxy_keeps_original_bytes_even_if_probe_would_fail(self):
        self.p.parent.mkdir(parents=True)
        original = "# managed by legacy desktop command\n" + make_block(URL)
        self.p.write_text(original)
        with patch("scripts.codex_proxy_env.probe",side_effect=UnsafeEnv("transient")) as checker:
            self.assertEqual(sync(self.p,URL)["state"],"unchanged")
            checker.assert_not_called()
        self.assertEqual(self.p.read_text(),original)
        self.assertFalse(self.p.parent.joinpath("proxy-env-backups").exists())

    def test_probed_failure_does_not_write_or_delete(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text("SAFE=1\n")
        with patch("scripts.codex_proxy_env.probe",side_effect=UnsafeEnv("offline")):
            with self.assertRaises(UnsafeEnv):sync(self.p,URL)
        self.assertEqual(self.p.read_text(),"SAFE=1\n")

    def test_sync_can_update_existing_owned_port_and_rollback(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text(make_block(ALT))
        self.assertEqual(state(self.p,URL)["state"],"different_route")
        self.assertEqual(sync(self.p,URL,test_proxy=False)["state"],"synced")
        self.assertEqual(state(self.p,URL)["state"],"synced")
        self.assertEqual(rollback(self.p)["state"],"rolled_back")

if __name__=="__main__": unittest.main()
