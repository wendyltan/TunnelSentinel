import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from scripts.computer_use_observer import scan, SOURCE
from workflow_health import evaluate, update_timeline

NOW = 1_793_110_000

class ComputerUseObserverTests(unittest.TestCase):
    def make_db(self, path, rows):
        c=sqlite3.connect(str(path))
        c.execute("CREATE TABLE thread_items (item_type TEXT, created_at_ms INTEGER, completed_at_ms INTEGER, item_json TEXT)")
        for status, at in rows:
            c.execute("INSERT INTO thread_items VALUES (?,?,?,?)",
                      ("mcpToolCall", (at-2)*1000, at*1000,
                       json.dumps({"server":"cua_repl","tool":"js","status":status,
                                   "arguments":"PRIVATE_PROMPT","result":"PRIVATE_SCREENSHOT"})))
        c.commit()
        c.close()

    def base(self, observation, now=NOW):
        return evaluate(now=now, healthy=True, proxy_available=True, deep={},
                        stream={},issues=[], computer_use=observation)

    def test_completed_invocation_is_only_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"history.db"
            self.make_db(db,[("completed",NOW-50)])
            result=scan(db=db,log_root=Path(folder),now=NOW,backend_state="running")
            self.assertEqual(result["execution"]["last_completed_at"],NOW-50)
            self.assertEqual(result["execution"]["recent_completed"],1)
            self.assertEqual(self.base(result)["computer_use"]["state"],"partial")
            self.assertIn("任务结果未验",self.base(result)["computer_use"]["label"])
            self.assertNotIn("PRIVATE_",json.dumps(result))

    def test_latest_failed_invocation_does_not_mean_proxy_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"history.db"
            self.make_db(db,[("completed",NOW-80),("failed",NOW-15)])
            result=scan(db=db,log_root=Path(folder),now=NOW,backend_state="running")
            state=self.base(result)
            self.assertEqual(state["computer_use"]["state"],"degraded")
            self.assertEqual(state["network"]["state"],"ok")

    def test_old_results_do_not_get_promoted(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"history.db"
            self.make_db(db,[("completed",NOW-3600)])
            result=scan(db=db,log_root=Path(folder),now=NOW,backend_state="running")
            self.assertEqual(self.base(result)["computer_use"]["state"],"partial")
            self.assertIn("控制服务",self.base(result)["computer_use"]["label"])
            result["backend"]["state"]="not_running"
            self.assertEqual(self.base(result)["computer_use"]["state"],"unknown")
            self.assertEqual(self.base(result,now=NOW+181)["computer_use"]["state"],"unknown")

    def test_startup_log_records_only_ready_not_tool_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            db=root/"history.db"
            self.make_db(db,[])
            dt=datetime.fromtimestamp(NOW,timezone.utc)
            p=root/dt.astimezone().strftime("%Y/%m/%d")
            p.mkdir(parents=True)
            date=datetime.fromtimestamp(NOW-10,timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            (p/"sample.log").write_text(date+" info [browser-session-registry] browser_use_iab_backend_startup_ready\n")
            result=scan(db=db,log_root=root,now=NOW,backend_state="running")
            self.assertEqual(result["backend"]["startup_ready_at"],NOW-10)
            self.assertEqual(result["execution"]["last_completed_at"],0)
            self.assertNotEqual(self.base(result)["computer_use"]["state"],"ok")

    def test_db_unavailable_and_stale_snapshot_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            result=scan(db=Path(folder)/"missing.db",log_root=Path(folder),now=NOW,backend_state="not_running")
            self.assertEqual(result["execution"]["state"],"unavailable")
            self.assertEqual(self.base(result)["computer_use"]["state"],"unknown")
            result["backend"]["state"]="running"
            self.assertEqual(self.base(result,now=NOW+190)["computer_use"]["state"],"unknown")

    def test_invocation_timeline_deduplicates_and_ignores_old_events(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"timeline.json"
            evidence={"source":SOURCE,"checked_at":NOW,
                      "execution":{"latest_at":NOW-20,"latest_status":"completed"}}
            axes=self.base(evidence)
            args=dict(now=NOW,axes=axes,proxy_client="system_proxy",stream={},
                      issues=[],egress_history=[],computer_use=evidence)
            a=update_timeline(path,**args)
            b=update_timeline(path,**args)
            self.assertEqual(sum(x["kind"]=="computer_use_invocation" for x in b["events"]),1)
            self.assertEqual(sum(x["kind"]=="computer_use_invocation" for x in a["events"]),1)
            self.assertNotIn("PRIVATE_",json.dumps(b))
            c=update_timeline(path,now=NOW+700,axes=axes,
                              proxy_client="system_proxy",stream={},issues=[],
                              egress_history=[],computer_use=evidence)
            self.assertEqual(sum(x["kind"]=="computer_use_invocation" for x in c["events"]),1)

if __name__=="__main__":
    unittest.main()
