#!/usr/bin/env python3
"""Count real Codex transport outcomes from its own read-only SQLite logs.

No login tokens, cookies, request bodies, or arbitrary URL paths are emitted.
Actual client metadata, NOT synthetic URL probes or intercepted TLS sessions.
"""
from __future__ import annotations
import re
import sqlite3
import time
from pathlib import Path

DB = Path.home() / '.codex/logs_2.sqlite'
ALLOW_PATHS = {'/backend-api/codex/models', '/backend-api/codex/responses', '/backend-api/codex/usage'}
WINDOW = 1800


def scan(path=DB, now=None):
    now = time.time() if now is None else now
    summary = {'source':'codex_client_read_only_sqlite','state':'unavailable',
               'window_seconds':WINDOW,'routes':[], 'websocket':{'successful_connects':0,'last_success_at':0},
               'limits':'client_log_metadata_only_not_authenticated_computer_use_proof',
               'checked_at':int(now)}
    try:
        con = sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=0.3)
        try:
            con.execute('PRAGMA query_only=ON')
            rows = con.execute('SELECT ts,target,feedback_log_body FROM '
                               '(SELECT ts,target,feedback_log_body FROM logs ORDER BY id DESC LIMIT 6000)'
                              ).fetchall()
        finally:con.close()
    except (sqlite3.Error,OSError):
        return summary
    counts={}
    connected=0
    lastws=0
    for stamp,target,body in rows:
        if not isinstance(stamp,int) or not 0<=now-stamp<=WINDOW:
            continue
        txt=str(body)
        if target=='codex_api::endpoint::responses_websocket':
            if 'successfully connected to websocket' in txt.lower():
                connected+=1
                lastws=max(lastws,stamp)
            continue
        if target not in ('codex_http_client::client','codex_http_client::default_client'):
            continue
        method=re.search(r'\bmethod=(GET|POST|PUT|DELETE)\b',txt)
        hostpath=re.search(r'https://chatgpt\.com(/backend-api/codex/[a-z_-]+)',txt)
        code=re.search(r'\bstatus=(\d{3})\b',txt)
        if not method or not hostpath or not code or hostpath.group(1) not in ALLOW_PATHS:
            continue
        key=(method.group(1),hostpath.group(1),int(code.group(1)))
        val=counts.setdefault(key,{'count':0,'last_at':0})
        val['count']+=1
        val['last_at']=max(val['last_at'],stamp)
    summary['state']='ok'
    summary['websocket']={'successful_connects':connected,'last_success_at':lastws}
    summary['routes']=[{'method':key[0],'path':key[1],'status':key[2],**val}
                       for key,val in sorted(counts.items())]
    return summary

if __name__=='__main__':
    import json
    print(json.dumps(scan(),ensure_ascii=False))
