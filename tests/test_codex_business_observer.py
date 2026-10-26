"""Real transport events are extracted only as redacted metadata from read-only SQLite."""
from pathlib import Path
import importlib.util,sqlite3,tempfile,time,unittest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('codex_business_observer',root/'scripts/codex_business_observer.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class BusinessLogTests(unittest.TestCase):
 def test_logged_actual_http_and_websocket_without_tokens(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'test.sqlite';conn=sqlite3.connect(path)
   conn.execute('CREATE TABLE logs (id INTEGER PRIMARY KEY, ts INTEGER, target TEXT, feedback_log_body TEXT)')
   now=int(time.time())
   conn.execute('INSERT INTO logs(ts,target,feedback_log_body) VALUES(?,?,?)',
       (now,'codex_http_client::client','Request completed method=GET url=https://chatgpt.com/backend-api/codex/models status=200; Authorization: Bearer PRIVATEFAKETOKEN'))
   conn.execute('INSERT INTO logs(ts,target,feedback_log_body) VALUES(?,?,?)',
       (now,'codex_api::endpoint::responses_websocket','successfully connected to websocket'))
   conn.execute('INSERT INTO logs(ts,target,feedback_log_body) VALUES(?,?,?)',
       (now,'codex_http_client::client','method=GET url=https://chatgpt.com/private/user-data status=200'))
   conn.commit();conn.close()
   result=mod.scan(path,now)
   self.assertEqual(result['state'],'ok')
   self.assertEqual(result['routes'],[{'method':'GET','path':'/backend-api/codex/models','status':200,'count':1,'last_at':now}])
   self.assertEqual(result['websocket']['successful_connects'],1)
   self.assertNotIn('PRIVATEFAKETOKEN',str(result))
 def test_no_database_is_unavailable(self):
  self.assertEqual(mod.scan(Path('/nonexistent/xyz.db'))['state'],'unavailable')
if __name__=='__main__':unittest.main()
