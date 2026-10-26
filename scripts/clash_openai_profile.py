#!/usr/bin/env python3
"""Construct a GPT-only Mihomo policy, no URLs/tokens embedded in source.

Importable via Clash Verge's per-profile Rules and Groups enhancements;
never change the generated profile or runtime directly from this module.
"""
from __future__ import annotations
import re

GROUP='TunnelSentinel-OpenAI'
DOMAINS=('chatgpt.com','openai.com','oaistatic.com','oaiusercontent.com',
         'oaistatsig.com','openaimerge.com')
EXCLUDE=r'(?i)(?:流量|到期|剩余|套餐|订阅|官网|expire|reset|traffic|[0-9]+(?:\.[0-9]+)?\s*G\s*\|)'

def make_group(initial: str) -> dict:
    if not initial or len(initial)>96 or ',' in initial:
        raise ValueError('invalid initial node')
    return {'name':GROUP,'type':'select','proxies':[initial],
            'include-all':True,'exclude-filter':EXCLUDE}

def prepend_rules()->list[str]:
    return ['DOMAIN-SUFFIX,'+domain+','+GROUP for domain in DOMAINS]

def patch_config(doc:dict,initial:str)->dict:
    from copy import deepcopy
    updated=deepcopy(doc)
    if not isinstance(updated.get('proxies'),list) or not isinstance(updated.get('proxy-groups'),list) or not isinstance(updated.get('rules'),list):
        raise ValueError('not a full Mihomo config')
    if initial not in {p.get('name') for p in updated['proxies']}:
        raise ValueError('initial node does not exist')
    if any(p.get('name')==GROUP for p in updated['proxy-groups']):
        raise ValueError('duplicate group')
    updated['proxy-groups'].insert(0,make_group(initial))
    updated['rules'] = prepend_rules()+updated['rules']
    return updated
