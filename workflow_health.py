#!/usr/bin/env python3
"""Evidence-led workflow state and bounded, privacy-preserving incident timeline.

A public probe is never promoted into authenticated ChatGPT, Codex generation,
or Computer Use success. Only aggregate method/path allowlist/status metadata.
No network calls, user content, tokens, account identifiers, or arbitrary URLs.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
from datetime import datetime

SOURCE='tunnelsentinel_workflow_evidence_v1'
SEVEN_DAYS=7*86400
MAX_EVENTS=240


def _axis(state, label, source, observed=0, detail=''):
    return {'state':state,'label':label,'source':source,
            'observed_at':int(observed or 0),'detail':detail}


def evaluate(*, now, healthy, proxy_available, deep, stream, issues):
    """Four independent axes; unknown means no business-level proof, not green."""
    network=_axis('ok' if healthy and proxy_available else 'failed',
                  '基础网络可达' if healthy and proxy_available else '代理或公共入口异常',
                  'guardian_public_edge_and_local_proxy',now)
    if not isinstance(deep,dict):deep={}
    stamp=int(deep.get('checked_at') or 0)
    fresh=(0<=now-stamp<=650) if stamp else False
    edge=next((x for x in deep.get('targets',[]) if isinstance(x,dict)
               and x.get('name')=='chatgpt_edge'),{}) if fresh else {}
    if not healthy or not proxy_available:
        chatgpt=_axis('degraded','当前公共网络异常 · 登录业务未验','guardian_public_edge_and_local_proxy',now)
    elif fresh and edge.get('state')=='reachable':
        chatgpt=_axis('partial','公开入口可达 · 登录业务未验','anonymous_public_probe',stamp)
    elif fresh and edge.get('state') in ('transport_failed','probe_unavailable'):
        chatgpt=_axis('degraded','公开入口异常 · 登录业务未验','anonymous_public_probe',stamp)
    else:
        chatgpt=_axis('unknown','尚无新鲜的 ChatGPT 业务证据','none',0)
    real=deep.get('real_codex_client',{}) if fresh else {}
    if not isinstance(real,dict) or real.get('state')!='ok':real={}
    routes=real.get('routes') or []
    success=[r for r in routes if isinstance(r,dict) and 200<=int(r.get('status',0))<300]
    last_success=max((int(r.get('last_at') or 0) for r in success), default=0)
    ws=real.get('websocket') or {}
    last_success=max(last_success,int(ws.get('last_success_at') or 0))
    recent=(stream or {}).get('recent_counts') or {}
    errors=sum(max(0,int(recent.get(k,0))) for k in ('broken_pipe','websocket_handshake','connection_reset'))
    stream_at=int((stream or {}).get('last_at') or 0)
    if (stream or {}).get('state')=='ok' and errors and 0<=now-stream_at<=300:
        codex=_axis('degraded','Codex 流连接近期出现异常','codex_client_read_only_sqlite',stream_at,
                    f'最近错误 {errors} 次')
    elif 0<=now-last_success<=1800 and last_success:
        codex=_axis('partial','检测到客户端真实请求 · 生成未验','codex_client_read_only_sqlite',last_success,
                    f'已记录成功 HTTP {len(success)} 类 / WS {int(ws.get("successful_connects",0))} 次')
    else:
        codex=_axis('unknown','近期没有可核实的 Codex 业务成功记录','none',0)
    browser_events=[x for x in issues if isinstance(x,dict)
                    and x.get('category')=='browser_backend'
                    and 0<=now-float(x.get('last_seen',0))<=300]
    if browser_events:
        last=max(int(x.get('last_seen',0)) for x in browser_events)
        browser=_axis('degraded','浏览器控制后端有错误日志','chatgpt_codex_client_log',last)
    else:
        browser=_axis('unknown','尚无真实 Computer Use 操作验收记录','none',0)
    return {'source':SOURCE,'checked_at':int(now),'network':network,
            'chatgpt':chatgpt,'codex':codex,'computer_use':browser,
            'note':'partial means transport/client-metadata evidence; not authenticated task success'}


def _read(path):
    try:
        j=json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(j,dict) and j.get('source')==SOURCE:return j
    except (ValueError,OSError,TypeError):pass
    return {'source':SOURCE,'events':[],'last_state':{},'last_event_markers':{},
            'active_incident':None,'quiet_samples':0}


def _save(path,obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    try:
        with tmp.open('w',encoding='utf-8') as f:
            json.dump(obj,f,ensure_ascii=False,separators=(',',':'))
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        try:tmp.unlink()
        except FileNotFoundError:pass


def update_timeline(path, *, now, axes, proxy_client, stream, issues, egress_history):
    """Deduplicate observations across cycles/restarts; no fabricated incidents."""
    data=_read(path)
    events=[x for x in data.get('events',[]) if isinstance(x,dict)
            and now-int(x.get('at',0))<=SEVEN_DAYS]
    marks=data.get('last_event_markers',{})
    states=data.get('last_state',{})
    active=data.get('active_incident')
    def add(kind, level, axis, title, observed=None, evidence=''):
        events.append({'at':int(observed if observed is not None else now),
                       'kind':kind,'level':level,'axis':axis,'title':title,
                       'source':evidence or SOURCE})
    before_owner=states.get('proxy_client')
    if before_owner and before_owner!=proxy_client:
        add('proxy_owner_changed','info','network','系统代理监测对象发生变化',evidence='macos_system_proxy')
    states['proxy_client']=proxy_client
    for name in ('network','chatgpt','codex','computer_use'):
        axis=axes[name]
        prior=states.get(name)
        state=axis['state']
        if prior and prior!=state:
            add('state_changed','warning' if state in ('failed','degraded') else 'info',name,
                axis['label'],evidence=axis['source'])
        states[name]=state
    last_error=int((stream or {}).get('last_at') or 0)
    count=sum(int(((stream or {}).get('recent_counts') or {}).get(k,0)) for k in
              ('broken_pipe','websocket_handshake','connection_reset'))
    if count and 0<=now-last_error<=300 and last_error>int(marks.get('codex_stream',0)):
        add('codex_stream_error','warning','codex','Codex 近期响应流出现连接异常',last_error,
            'codex_read_only_sqlite')
        marks['codex_stream']=last_error
    for issue in issues:
        if not isinstance(issue,dict):continue
        kind=issue.get('category')
        if kind not in ('browser_backend','cloudflare','thread_sync','rate_limit'):continue
        last=int(issue.get('last_seen',0) or 0)
        marker='issue_'+kind
        if last and 0<=now-last<=300 and last>int(marks.get(marker,0)):
            add('client_log_issue','warning' if kind=='browser_backend' else 'info',
                'computer_use' if kind=='browser_backend' else 'chatgpt',
                '客户端日志出现'+{'browser_backend':'浏览器控制后端异常','cloudflare':'验证挑战',
                                 'thread_sync':'同步异常','rate_limit':'限流提示'}[kind],
                last,'client_log_classifier')
            marks[marker]=last
    if isinstance(egress_history,list):
        for item in egress_history[-5:]:
            if not isinstance(item,dict):continue
            key=str(item.get('observed_at') or '')
            if key and key!=marks.get('egress_change'):
                # Only append new event once; never leak actual IP here.
                try: stamp=int(datetime.fromisoformat(key).timestamp())
                except (ValueError,TypeError):continue
                if 0<=now-stamp<=SEVEN_DAYS and stamp>int(marks.get('egress_epoch',0)):
                    add('public_egress_changed','info','network','公共出口区域已变化（不代表代理节点）',stamp,
                        'public_trace_two_sample_confirmation')
                    marks['egress_change']=key
                    marks['egress_epoch']=stamp
    # Incident is high-confidence at network failure OR a client-observed
    # Codex/Computer Use fault. We do not open an incident for missing evidence.
    failing=[k for k in ('network','codex','computer_use')
             if axes[k]['state'] in ('failed','degraded')]
    if failing:
        data['quiet_samples']=0
        if not active:
            active={'id':f'{int(now)}-incident','started_at':int(now),
                    'axes':list(failing),'phase':'active'}
            add('incident_started','warning',failing[0],'检测到影响网络或客户端的异常')
        else:
            active['axes']=list(dict.fromkeys(active.get('axes',[])+failing))
    elif active:
        data['quiet_samples']=int(data.get('quiet_samples',0))+1
        if data['quiet_samples']>=2:
            add('incident_resolved','info','workflow','连续两轮未检测到相同异常；业务恢复仍需实际验证')
            active=None
            data['quiet_samples']=0
    data.update({'events':events[-MAX_EVENTS:],'last_state':states,
                 'last_event_markers':marks,'active_incident':active,'updated_at':int(now)})
    _save(path,data)
    return {'source':SOURCE,'checked_at':int(now),'events':events[-30:],
            'active_incident':active,'history_window_seconds':SEVEN_DAYS,
            'scope':'metadata_only_no_task_content'}
