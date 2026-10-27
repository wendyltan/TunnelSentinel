#!/usr/bin/env python3
"""Bounded, credential-free layer checks for ChatGPT, Codex and browser transport.

Never tests authenticated actions, changes routes, loads conversation content,
or records raw URLs, IP addresses, headers, cookies, or response bodies.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys
import time
from urllib.parse import urlparse

# Match the Guardian's actual primary public-edge probe. Slow but valid
# HTTPS handshakes must not fail at 6s in one detector and succeed at 10s in another.
CONNECT_TIMEOUT_SECONDS = 5
MAX_REQUEST_SECONDS = 10
PROCESS_TIMEOUT_SECONDS = 12

# Every destination is intentionally fixed; never accept an arbitrary URL from config.
TARGETS = (
    ('chatgpt_edge','https://chatgpt.com/cdn-cgi/trace','http200'),
    ('chatgpt_websocket','https://ws.chatgpt.com/','wss_handshake'),
    ('codex_websocket','https://chatgpt.com/','wss_handshake'),
    ('openai_api_tls','https://api.openai.com/','tls_only'),
    ('openai_auth_tls','https://auth.openai.com/','tls_only'),
    ('chatgpt_desktop_tls','https://desktop.chat.openai.com/','tls_only'),
)

def classify(exit_code:int, http_code:int, kind:str)->str:
    if http_code <= 0: return 'transport_failed'
    # curl may see the real HTTP status (e.g. 403) and then fail while reading
    # the response body. This is not TLS unreachable, nor a successful request.
    if exit_code != 0: return 'http_response_with_transfer_error'
    if kind=='http200':
        if http_code==200:return 'reachable'
        if http_code in (403,429):return 'challenge_or_rate_limit'
        return 'http_unexpected'
    if kind=='wss_handshake':
        if http_code==101:return 'upgrade_accepted'
        if http_code in (400,401,403,404,405,421,426,429):return 'tls_reachable_auth_or_path_unverified'
        if 200<=http_code<500:return 'tls_reachable_path_unverified'
        return 'http_unexpected'
    if 100<=http_code<500:return 'tls_reachable_not_authenticated'
    return 'http_unexpected'

def test_target(item, proxy:str)->dict:
    name,url,kind=item
    # This does not reuse ChatGPT/Codex's authenticated endpoint path or token.
    method='HTTP/1.1 GET / + Upgrade: websocket (anonymous synthetic)' if kind=='wss_handshake' else ('HTTPS GET /cdn-cgi/trace (public)' if kind=='http200' else 'HTTPS GET / (anonymous TLS/HTTP)')
    cmd=['/usr/bin/curl','--silent','--show-error',
         '--proxy',proxy] if proxy else ['/usr/bin/curl','--silent','--show-error','--noproxy','*']
    cmd.extend(['--connect-timeout',str(CONNECT_TIMEOUT_SECONDS),
                '--max-time',str(MAX_REQUEST_SECONDS),'--output','/dev/null',
                '--write-out','%{http_code} %{time_total}'])
    if kind=='wss_handshake':
        cmd.extend(['--http1.1','--header','Connection: Upgrade',
                    '--header','Upgrade: websocket','--header','Sec-WebSocket-Version: 13',
                    '--header','Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=='])
    cmd.append(url)
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=PROCESS_TIMEOUT_SECONDS,check=False)
        fields=result.stdout.strip().split()
        http=int(fields[0]) if fields and fields[0].isdigit() else 0
        ms=round(float(fields[1])*1000) if len(fields)>1 else None
        return {'name':name,'state':classify(result.returncode,http,kind),
                'http_code':http,'latency_ms':ms,'curl_exit':result.returncode,
                'observed_at':int(time.time()),
                'probe_method':method,'scope':'anonymous_transport_not_authenticated_business'}
    except (OSError,ValueError,IndexError,subprocess.SubprocessError):
        return {'name':name,'state':'probe_unavailable','http_code':0,'latency_ms':None,
                'probe_method':method,'scope':'anonymous_transport_not_authenticated_business'}

def scan(proxy:str)->dict:
    parsed=urlparse(proxy)
    # Guardian passes ONLY the vetted macOS system proxy or an empty string
    # for the current no-explicit-proxy/TUN route. No subscription URLs or
    # embedded proxy credentials are accepted.
    allowed = (not proxy) or (parsed.scheme in ('http','https','socks5','socks5h')
              and parsed.hostname and parsed.port and 1 <= parsed.port <= 65535
              and parsed.username is None and parsed.password is None
              and not parsed.path and not parsed.query and not parsed.fragment)
    if not allowed:
        return {'source':'bounded_public_tls_probes','state':'invalid_system_proxy','checked_at':int(time.time()),'targets':[]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes=list(pool.map(lambda item:test_target(item,proxy),TARGETS))
    states={x['name']:x['state'] for x in outcomes}
    # A desktop host's anonymous TLS handshake is NOT a verdict on Computer Use.
    try:
        from codex_business_observer import scan as observe_real_codex
        real_codex = observe_real_codex()
    except (ImportError,RuntimeError,OSError):
        real_codex = {'source':'codex_client_read_only_sqlite','state':'unavailable','routes':[]}
    return {'source':'bounded_public_tls_probes','state':'completed',
            'real_codex_client':real_codex,
            'checked_at':int(time.time()),'targets':outcomes,
            'public_edge_ok':states.get('chatgpt_edge')=='reachable',
            'websocket_transport_ok':states.get('chatgpt_websocket')=='upgrade_accepted',
            'websocket_host_http_reachable':states.get('chatgpt_websocket') in
                ('upgrade_accepted','tls_reachable_auth_or_path_unverified','tls_reachable_path_unverified','http_response_with_transfer_error'),
            'codex_websocket_upgrade_verified':states.get('codex_websocket')=='upgrade_accepted',
            'limitations':'anonymous_GET_not_actual_authenticated_ChatGPT_Codex_or_computer_use'}

if __name__=='__main__':
    # Sole argument is the already confirmed localhost proxy supplied by Guardian.
    if len(sys.argv)!=2:
        sys.exit(2)
    print(json.dumps(scan(sys.argv[1]),ensure_ascii=False,separators=(',',':')))
