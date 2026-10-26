#!/usr/bin/env python3
"""Bounded, real Mihomo GPT-only failover. No second proxy core.

Writes ONLY /proxies/TunnelSentinel-OpenAI using the local Unix socket after
policy/readiness checks, then verifies policy readback, public edge and shared
policy integrity. Real Codex stream success is a separate evidence layer.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote
from clash_observer import UnixHTTP, api, inspect, read_socket_path
from clash_openai_profile import GROUP, DOMAINS

ROOT=Path.home()/'Library/Application Support/OpenAILinkGuardian'
STATE=ROOT/'clash_route_state.json'
REPORT=ROOT/'clash_failover_status.json'
LOCK=ROOT/'clash_failover.lock'
MIN_DELAY_MS=1
MAX_DELAY_MS=2500
COOLDOWN_S=600
QUARANTINE_S=1800


def request(path:str,method='GET',data=None):
    if method not in ('GET','PUT'):raise ValueError('invalid method')
    if method=='PUT' and path != '/proxies/'+quote(GROUP,safe=''):
        raise ValueError('writes only permitted to GPT-only group')
    s=read_socket_path()
    if not s:raise OSError('Mihomo Unix socket not available')
    c=UnixHTTP(s)
    try:
        encoded=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
        c.request(method,path,body=encoded,headers={'Content-Type':'application/json'} if encoded else {})
        r=c.getresponse();body=r.read(2_000_001)
        if r.status not in (200,204):raise OSError(f'API HTTP {r.status}')
        if len(body)>2_000_000:raise ValueError('API response too large')
        return json.loads(body) if body else {}
    finally:c.close()

def atomic_json(path:Path, data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def load(path:Path)->dict:
    try:
        obj=json.loads(path.read_text())
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError):return {}

def allowed_node(name:str,node:dict)->bool:
    if node.get('type') in ('Selector','Fallback','URLTest','LoadBalance','Direct','Reject','Pass','Compatible'):return False
    return not bool(re.search(r'(?:\d+(?:\.\d+)?\s*G\s*\||traffic|reset|expire|quota|到期|剩余|套餐|官网|订阅|流量)',name,re.I))

def validated_context():
    live=inspect()
    if not live.get('active') or live.get('mode') != 'rule' or live.get('tun_enabled'):
        raise RuntimeError('Clash is not the verified rule-mode system proxy')
    conf=request('/configs')
    from urllib.parse import urlparse
    active_port = urlparse(str(live.get('proxy_url',''))).port
    if conf.get('mode') != 'rule' or conf.get('mixed-port') != active_port or not active_port or (conf.get('tun') or {}).get('enable'):
        raise RuntimeError('unexpected active config')
    rules=request('/rules').get('rules',[])
    if len(rules)<len(DOMAINS) or any(x.get('proxy')!=GROUP or x.get('payload')!=d or x.get('type')!='DomainSuffix' for x,d in zip(rules[:len(DOMAINS)],DOMAINS)):
        raise RuntimeError('GPT-only routing rules are missing or reordered')
    proxies=request('/proxies').get('proxies',{})
    grp=proxies.get(GROUP) or {}
    if grp.get('type')!='Selector' or len(grp.get('all',[]))<2:
        raise RuntimeError('GPT-only Selector missing or empty')
    if 'Proxies' not in proxies or 'AI' not in proxies:
        raise RuntimeError('shared policies not found')
    original=grp.get('now','')
    if original not in grp['all'] or not allowed_node(original,proxies.get(original,{})):
        raise RuntimeError('current GPT-only selection invalid')
    if grp.get('now')=='Proxies':raise RuntimeError('unsafe shared selection')
    return proxies,grp,original

def latency_test(name:str)->int|None:
    from urllib.parse import urlencode
    path='/proxies/'+quote(name,safe='')+'/delay?'+urlencode({'url':'https://chatgpt.com/robots.txt','timeout':4000,'expected':'200-299'})
    try:
        value=request(path).get('delay')
        return int(value) if isinstance(value,(int,float)) and MIN_DELAY_MS<=value<=MAX_DELAY_MS else None
    except (OSError,ValueError,TypeError,TimeoutError):return None

def rank_choices(proxies:dict, grp:dict,current:str, excluded:dict)->list[str]:
    now=time.time()
    out=[]
    for name in grp['all']:
        node=proxies.get(name,{})
        if name==current or not allowed_node(name,node) or float(excluded.get(name,0))>now:continue
        # Prefer regional endpoints with consistent prior use rather than a
        # metadata node or a provider record. Real health check still required.
        region=(0 if any(t in name.lower() for t in ('japan','日本','tokyo')) else
                1 if any(t in name.lower() for t in ('singapore','新加坡','hong kong','香港')) else
                2 if any(t in name.lower() for t in ('usa','united states','美国')) else 3)
        history=node.get('history') or []
        last=(history[-1] if history and isinstance(history[-1],dict) else {})
        delay=last.get('delay')
        if not isinstance(delay,(int,float)) or delay<=0:delay=10000
        out.append((region,delay,name))
    out.sort()
    return [name for _,_,name in out[:12]]

def select_candidate(proxies,grp,current,excluded):
    scored=[]
    for name in rank_choices(proxies,grp,current,excluded)[:6]:
        ms=latency_test(name)
        if ms is not None:scored.append((ms,name))
    if not scored:return None
    scored.sort()
    return scored[0][1]

def put_selection(node:str,grp:dict):
    if node not in grp.get('all',[]):raise RuntimeError('target not in dedicated group')
    request('/proxies/'+quote(GROUP,safe=''),'PUT',{'name':node})
    updated=request('/proxies').get('proxies',{})
    if updated.get(GROUP,{}).get('now')!=node:raise RuntimeError('selection failed readback')
    return updated

def verify_public_edge() -> bool:
    live=inspect()
    if not live.get('active') or live.get('mode')!='rule':return False
    proxy=str(live.get('proxy_url',''))
    from urllib.parse import urlparse
    parsed=urlparse(proxy)
    if parsed.hostname!='127.0.0.1' or not (parsed.port and 1<=parsed.port<=65535):return False
    p=subprocess.run(['/usr/bin/curl','--proxy',proxy,'--connect-timeout','4','--max-time','10','--silent','--show-error','--output','/dev/null','--write-out','%{http_code}','https://chatgpt.com/cdn-cgi/trace'],capture_output=True,text=True,timeout=12)
    return p.returncode==0 and p.stdout.strip()=='200'

def perform_switch(proxies,grp,original,target,do_restore=False):
    shared=proxies['Proxies'].get('now');ai=proxies['AI'].get('now')
    if target==original or not allowed_node(target,proxies.get(target,{})):
        raise RuntimeError('unsafe target')
    try:
        after=put_selection(target,grp)
        if after['Proxies'].get('now')!=shared or after['AI'].get('now')!=ai:
            raise RuntimeError('shared proxy unexpectedly changed')
        if not verify_public_edge():raise RuntimeError('GPT public edge failed after switch')
        if do_restore:
            put_selection(original,grp)
            if not verify_public_edge():raise RuntimeError('original GPT public edge failed after restore')
        return {'ok':True,'original':original,'target':target,'restored':do_restore,'business_verified':False}
    except Exception:
        try:put_selection(original,grp)
        except Exception:pass
        raise

def do_once(canary=False)->dict:
    conf=load(ROOT/'config.json')
    if not conf.get('automatic_control_enabled',False):
        return {'state':'monitor_only','changed':False}
    if not canary and not conf.get('clash_auto_failover_enabled',False):
        return {'state':'disabled','changed':False}
    observed=load(ROOT/'status.json')
    if observed.get('proxy_client')!='clash' or observed.get('route_management')!='clash_observe_only':
        return {'state':'backend_unverified','changed':False}
    age=time.time()-(ROOT/'status.json').stat().st_mtime
    if age<0 or age>100:
        return {'state':'status_stale','changed':False}
    # A real, repeated *transport* outage may make the current public probe
    # unhealthy. Do not prohibit failover precisely when its path is dead.
    # Cloudflare 403 challenges and 429 rate limits have HTTP responses, so
    # they are explicitly excluded from this independent outage trigger.
    edge_probes=[p for p in (observed.get('probes') or [])
                 if isinstance(p,dict) and str(p.get('name','')).startswith('edge')]
    transport_outage=(not observed.get('healthy')
        and observed.get('proxy_available') is True
        and int(observed.get('recent_failure_score',0))>=3
        and bool(edge_probes)
        and all(int(p.get('http_code',0))==0 for p in edge_probes))
    trigger_source='transport_outage' if transport_outage else 'codex_stream'
    if not canary:
        stream=observed.get('codex_stream_diagnostics') or {}
        fresh_stream=(conf.get('codex_stream_sqlite_monitor_enabled')
            and stream.get('state')=='ok'
            and 0<=time.time()-int(stream.get('scan_at',0))<=100)
        if not fresh_stream and not transport_outage:
            return {'state':'stream_evidence_stale','changed':False}
        last=int(stream.get('last_at',0))
        count=sum(int((stream.get('recent_counts') or {}).get(k,0)) for k in ('broken_pipe','websocket_handshake','connection_reset')) if fresh_stream else 0
        recent_stream=bool(count>=3 and 0<=time.time()-last<=210)
        if not (recent_stream or transport_outage):
            return {'state':'armed','changed':False,'recent_errors':count}
    state=load(STATE);now=time.time();day=time.strftime('%Y-%m-%d')
    if state.get('day')!=day:
        state={'day':day,'actions_today':0,'quarantine':{},'last_at':float(state.get('last_at',0))}
    if not canary:
        if state.get('actions_today',0)>=3 or now-float(state.get('last_at',0))<COOLDOWN_S:
            return {'state':'cooldown_or_daily_limit','changed':False}
    proxies,grp,current=validated_context()
    excluded={name:until for name,until in (state.get('quarantine') or {}).items() if float(until)>now}
    if len(excluded)>=2 and not canary:return {'state':'quarantine_limit','changed':False}
    target=select_candidate(proxies,grp,current,excluded)
    if not target:return {'state':'no_healthy_alternative','changed':False}
    outcome=perform_switch(proxies,grp,current,target,do_restore=canary)
    if not canary:
        state.update({'last_at':now,'actions_today':int(state.get('actions_today',0))+1,'last_node':target,
                      'previous_node':current,'quarantine':{**excluded,current:now+QUARANTINE_S},
                      'last_error_at':int((observed.get('codex_stream_diagnostics') or {}).get('last_at',0))})
        atomic_json(STATE,state)
    return {'state':'canary_passed' if canary else 'route_changed_business_pending','changed':not canary,
            'trigger_source':'canary' if canary else trigger_source,
            'from':current,'to':target,'restored':canary,'route_verified':True,
            'business_verified':False,'actions_today':int(state.get('actions_today',0))}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--canary',action='store_true');args=parser.parse_args()
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with open(LOCK,'a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:
            outcome=do_once(args.canary)
        except Exception as ex:
            outcome={'state':'failed_closed','changed':False,'error_type':type(ex).__name__}
        outcome['checked_at']=int(time.time())
        atomic_json(REPORT,outcome)
        print(json.dumps(outcome,ensure_ascii=False))
    return 0 if outcome['state'] not in ('failed_closed',) else 1

if __name__=='__main__':sys.exit(main())
