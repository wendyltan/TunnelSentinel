#!/usr/bin/env python3
"""Read-only, localhost-only Mihomo observer. Never changes proxy settings.

Outputs only the OpenAI group route and a bounded candidate assessment; does
not emit request URLs, subscription URLs, credentials, or other website traffic.
"""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

CLASH_ROOT = Path.home() / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev'
GPT_HOSTS = ('openai.com', 'chatgpt.com', 'oaistatic.com', 'oaiusercontent.com', 'oaistatsig.com', 'openaimerge.com')

class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path: str):
        super().__init__('localhost', timeout=1.4)
        self.path = path
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(1.4)
        self.sock.connect(self.path)

def read_socket_path(path: Path = CLASH_ROOT / 'clash-verge.yaml') -> str:
    if not path.is_file(): return ''
    content = path.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'^external-controller-unix:\s*[\x27\x22]?([^\x27\x22\n#]+)', content, re.M)
    if not m: return ''
    v = m.group(1).strip()
    try:
        st = os.stat(v)
        if st.st_uid != os.geteuid() or not stat.S_ISSOCK(st.st_mode): return ''
    except OSError: return ''
    return v if (v.startswith('/var/folders/') or v.startswith('/private/var/folders/')) else ''

def api(path: str, route: str) -> dict:
    if route not in ('/configs', '/proxies', '/connections', '/providers/proxies', '/version'):
        raise ValueError('non-allowlisted API request')
    c = UnixHTTP(path)
    try:
        c.request('GET', route)
        response = c.getresponse()
        if response.status != 200: raise OSError('API returned HTTP %d' % response.status)
        data = response.read(2_000_001)
        if len(data) > 2_000_000: raise ValueError('API response too large')
        result = json.loads(data)
        if not isinstance(result, dict): raise ValueError('unexpected response')
        return result
    finally: c.close()

def system_proxy() -> tuple[str, int]:
    try:
        p = subprocess.run(['/usr/sbin/scutil','--proxy'],capture_output=True,text=True,timeout=2)
        if p.returncode: return '', 0
        data = {}
        for key,value in re.findall(r'^\s*(HTTPEnable|HTTPProxy|HTTPPort|HTTPSEnable|HTTPSProxy|HTTPSPort)\s*:\s*([^\n]+)',p.stdout,re.M):
            data[key] = value.strip()
        if data.get('HTTPEnable')!='1' or data.get('HTTPSEnable')!='1':return '',0
        if data.get('HTTPProxy') not in ('127.0.0.1','localhost') or data.get('HTTPSProxy') != data.get('HTTPProxy'):return '',0
        if data.get('HTTPSPort') != data.get('HTTPPort'):return '',0
        return data.get('HTTPProxy',''),int(data.get('HTTPPort',0))
    except (OSError,ValueError,subprocess.TimeoutExpired):return '',0

def is_gpt_host(host: str)->bool:
    host=host.lower().strip('.')
    return bool(host) and any(host==v or host.endswith('.'+v) for v in GPT_HOSTS)

def evaluate_candidate(name: str, item: dict, now: str) -> dict:
    typ=item.get('type','')
    history=item.get('history') if isinstance(item.get('history'),list) else []
    last=history[-1] if history else {}
    delay=last.get('delay') if isinstance(last,dict) else None
    bad_type=typ in ('Selector','Fallback','URLTest','LoadBalance','Reject','Direct','Pass','Compatible')
    quota=bool(re.search(r'(?:\bquota\b|\d+(?:\.\d+)?\s*G\s*\||剩余流量|到期|官网|套餐|订阅)',name,re.I))
    valid_delay=isinstance(delay,(int,float)) and 0<delay<3000
    return {'name':name[:95],'type':str(typ)[:35],'eligible':bool(not bad_type and not quota and valid_delay),'reason':('group_or_direct' if bad_type else 'metadata_label' if quota else 'no_recent_healthy_latency' if not valid_delay else 'recent_transport_sample'), 'delay_ms':int(delay) if valid_delay else None,'selected':name==now}

def summarize(config: dict, proxies: dict, connections: dict) -> dict:
    allproxies=proxies.get('proxies') or {}
    if not isinstance(allproxies,dict):allproxies={}
    dedicated = 'TunnelSentinel-OpenAI' in allproxies
    observed_group = 'TunnelSentinel-OpenAI' if dedicated else 'AI'
    group=allproxies.get(observed_group) or {}
    ai_chain=[];current='';observed_nodes=set();sample_count=0;selected='';group_name=''
    if group.get('type') in ('Selector','Fallback','URLTest','LoadBalance'):
        selected=group.get('now') or ''
        group_name=observed_group
    for entry in (connections.get('connections') or [])[:800]:
        if not isinstance(entry,dict):continue
        md=entry.get('metadata') or {}
        if not is_gpt_host(str(md.get('host') or '')):continue
        chain=entry.get('chains') or []
        if not isinstance(chain,list) or not chain:continue
        if observed_group not in chain: continue
        sample_count+=1
        if not ai_chain: ai_chain=[str(v)[:100] for v in chain[:8]]
        observed_nodes.add(str(chain[0])[:95])
    # Mixed chains during a transition mean there is NO single current node.
    current=next(iter(observed_nodes)) if len(observed_nodes)==1 else ''
    if len(observed_nodes)>1:ai_chain=[]
    parent=selected if isinstance(selected,str) else ''
    downstream=allproxies.get(parent) or {}
    if dedicated:
        # Unlike legacy AI→Proxies, the dedicated policy selects direct nodes;
        # never point mutation at the shared Proxies group.
        downstream=group
        candidates=group.get('all') if isinstance(group.get('all'),list) else []
    else:
        candidates=downstream.get('all') if isinstance(downstream.get('all'),list) else []
        if not candidates: candidates=group.get('all') if isinstance(group.get('all'),list) else []
    candidate_list=[]
    for name in candidates[:250]:
        if isinstance(name,str) and name in allproxies:
            candidate_list.append(evaluate_candidate(name,allproxies[name],group.get('now','') if dedicated else downstream.get('now','')))
    eligible=[x for x in candidate_list if x['eligible']]
    mode=str(config.get('mode','unknown')).lower()
    return {'source':'mihomo_unix_readonly','observed_at':int(time.time()),'mode':mode,'tun_enabled':bool((config.get('tun') or {}).get('enable')) if isinstance(config.get('tun'),dict) else False,'ai_group':group_name,'ai_group_type':str(group.get('type',''))[:24],'ai_selection':str(selected)[:95], 'child_group_type':str(downstream.get('type',''))[:24],'selected_node':str(group.get('now','') if dedicated else downstream.get('now',''))[:95], 'active_request_node':current if sample_count else '', 'active_request_chain':ai_chain, 'active_gpt_connections':sample_count, 'candidate_count':len(candidate_list),'eligible_count':len(eligible),'dry_run_candidate':min(eligible,key=lambda x:x['delay_ms'])['name'] if eligible else '', 'switch_simulation':('dedicated_policy_ready_for_guarded_failover' if eligible else 'insufficient_evidence_no_write') if dedicated else ('shared_ai_policy_requires_dedicated_openai_group' if eligible else 'insufficient_evidence_no_write'),'switch_write_enabled':False,'scope':'dedicated_openai_policy' if dedicated else 'shared_ai_policy','active_proxy_count':len(allproxies)}

def inspect() -> dict:
    addr,port=system_proxy()
    if not addr or not (0<port<65536): return {'active':False,'source':'macos_system_proxy','reason':'clash_not_system_proxy'}
    path=read_socket_path()
    if not path:return {'active':False,'source':'mihomo_unix_readonly','reason':'socket_unavailable'}
    try:
        config=api(path,'/configs')
        configured_port=int(config.get('mixed-port',0))
        if configured_port != port or configured_port <= 0: return {'active':False,'source':'mihomo_unix_readonly','reason':'proxy_port_mismatch','system_proxy_port':port}
        result=summarize(config,api(path,'/proxies'),api(path,'/connections'))
        result.update({'active':True,'proxy_url':f'http://127.0.0.1:{port}','api_healthy':True})
        return result
    except (OSError,ValueError,TypeError,KeyError,ConnectionError,TimeoutError,http.client.HTTPException) as exc:
        return {'active':False,'source':'mihomo_unix_readonly','reason':type(exc).__name__}

if __name__=='__main__':
    print(json.dumps(inspect(),ensure_ascii=False,separators=(',',':')))
