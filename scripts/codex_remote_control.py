# Remote Control metadata parser
from __future__ import annotations
import re
import sqlite3
import time
from pathlib import Path

DB = Path.home() / ".codex/logs_2.sqlite"
TARGET = "codex_app_server_transport::transport::remote_control::websocket"
WINDOW = 3600

def scan(path=DB, now=None):
    now = time.time() if now is None else now
    out = {"source":"codex_remote_control_read_only_sqlite","state":"unavailable",
           "checked_at":int(now),"connection_state":"unknown",
           "last_disconnect_at":0,"last_connected_at":0,"sessions":[]}
    try:
        con = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True,timeout=0.3)
        try:
            con.execute("PRAGMA query_only=ON")
            rows = con.execute("SELECT ts,feedback_log_body FROM "
                 "logs WHERE target=? AND ts>=? ORDER BY ts DESC LIMIT 3000",
                 (TARGET,int(now-WINDOW))).fetchall()
        finally:
            con.close()
    except (sqlite3.Error,OSError):
        return out
    sessions = []
    current = None
    connected_at = 0
    for stamp, body in sorted(rows,key=lambda r:r[0] if isinstance(r[0],int) else -1):
        if not isinstance(stamp,int) or not 0 <= now-stamp <= WINDOW:
            continue
        text = str(body).lower()
        if "remote control websocket reader disconnected" in text:
            if current is not None:
                current["state"]="unverified"
                sessions.append(current)
            current = {"disconnected_at":stamp,"reconnected_at":0,
                       "duration_seconds":None,"retries":0,
                       "connect_failures":0,"state":"reconnecting"}
        elif "connected to app-server remote control websocket" in text:
            connected_at = max(connected_at,stamp)
            if current is not None:
                current["reconnected_at"]=stamp
                current["duration_seconds"]=max(0,stamp-current["disconnected_at"])
                current["state"]="reconnected"
                sessions.append(current)
                current=None
        elif current is not None and "reconnect_attempt=" in text:
            match=re.search(r"reconnect_attempt=(\d+)",text)
            if match:
                current["retries"]=max(current["retries"],int(match.group(1)))
        elif current is not None and "failed to connect to app-server remote control websocket" in text:
            current["connect_failures"]+=1
    # finalize sessions
    if current:
        sessions += [current]
    sessions = sessions[-24:]
    latest = max([item['disconnected_at'] for item in sessions] or [0])
    connection_state = 'reconnecting' if sessions and sessions[-1]['state'] == 'reconnecting' else 'unknown'
    if connected_at and connected_at >= latest and connection_state != 'reconnecting':
        connection_state = 'connected'
    out['state'] = 'ok'
    out['sessions'] = sessions
    out['last_disconnect_at'] = latest
    out['last_connected_at'] = connected_at
    out['connection_state'] = connection_state
    return out

if __name__ == '__main__':
    import json
    print(json.dumps(scan(),ensure_ascii=False))
