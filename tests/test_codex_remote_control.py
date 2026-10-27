import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.codex_remote_control import scan, TARGET
from workflow_health import evaluate, update_timeline

BASE = 1793067000

class RemoteControlTests(unittest.TestCase):
    def make_db(self, path):
        c=sqlite3.connect(path)
        c.execute('CREATE TABLE logs (id INTEGER PRIMARY KEY,ts INTEGER,target TEXT,feedback_log_body TEXT)')
        messages=[
            (BASE,'remote control websocket reader disconnected'),
            (BASE+2,'reconnect_attempt=2'),
            (BASE+4,'failed to connect to app-server remote control websocket'),
            (BASE+12,'reconnect_attempt=3'),
            (BASE+18,'connected to app-server remote control websocket'),
        ]
        for ts,body in messages:
            c.execute('INSERT INTO logs(ts,target,feedback_log_body) VALUES(?,?,?)',
                     (ts,TARGET,body))
        c.commit();c.close()

    def test_one_recovery_cycle_not_multiple_retries(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'events.sqlite'
            self.make_db(path)
            r=scan(path,BASE+25)
            self.assertEqual(len(r['sessions']),1)
            e=r['sessions'][0]
            self.assertEqual(e['duration_seconds'],18)
            self.assertEqual(e['retries'],3)
            self.assertEqual(e['connect_failures'],1)
            self.assertEqual(r['connection_state'],'connected')
    def test_live_reconnecting_state(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.sqlite'
            self.make_db(p)
            r=scan(p,BASE+10)
            self.assertEqual(r['connection_state'],'reconnecting')
            stream={'state':'ok','remote_control':r}
            axes=evaluate(now=BASE+10,healthy=True,proxy_available=True,
                          deep={},stream=stream,issues=[])
            self.assertEqual(axes['codex']['state'],'degraded')
    def test_timeline_one_cycle_after_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.sqlite'
            self.make_db(p)
            timeline=Path(td)/'timeline.json'
            for now in (BASE+10,BASE+25,BASE+55):
                r=scan(p,now)
                stream={'state':'ok','remote_control':r}
                axes=evaluate(now=now,healthy=True,proxy_available=True,
                              deep={},stream=stream,issues=[])
                result=update_timeline(timeline,now=now,axes=axes,
                              proxy_client='shadowrocket',stream=stream,
                              issues=[],egress_history=[])
            records=[e for e in result['events'] if e['kind']=='codex_remote_session']
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]['duration_seconds'],18)
            self.assertEqual(records[0]['retries'],3)

if __name__=='__main__':
    unittest.main()
