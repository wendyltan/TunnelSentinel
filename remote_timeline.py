"""Merge privacy-safe Codex Remote Control lifecycle summaries into event history."""

def merge(events, remote, now):
    if not isinstance(remote,dict) or remote.get('state') != 'ok':
        return
    for item in remote.get('sessions', []):
        if not isinstance(item,dict):
            continue
        started=int(item.get('disconnected_at') or 0)
        if not started or not 0<=now-started<=3600:
            continue
        ended=int(item.get('reconnected_at') or 0)
        row={'at':started,'kind':'codex_remote_session','axis':'codex',
             'level':'info' if ended else 'warning',
             'title':'远程控制连接已恢复' if ended else '远程控制正在重新连接',
             'source':'codex_remote_control_read_only_sqlite',
             'reconnected_at':ended,'duration_seconds':max(0,ended-started) if ended else None,
             'retries':min(99,max(0,int(item.get('retries') or 0))),
             'connect_failures':min(99,max(0,int(item.get('connect_failures') or 0)))}
        previous=next((i for i,e in enumerate(events)
                       if e.get('kind')=='codex_remote_session' and e.get('at')==started),None)
        if previous is None:
            events.append(row)
        else:
            events[previous].update(row)
