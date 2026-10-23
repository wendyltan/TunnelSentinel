# OpenAI routing and passive failover audit · 2026-10-23

## Scope and evidence

Mac mini Shadowrocket 2.2.92; active copy: `sr_cnip-copy.conf-984549565.db` (confirmed 2026-10-23 by prior GUI and preferences; verify again before any edit). OpenAI business route: `OpenAI-Resilience` native fallback with subscription-backed candidates filtered by `JAPAN 04|JAPAN 14|SEATTLE 05|SAN JOSE 07`, 60-second interval, 5-second timeout, public probe URL `https://chatgpt.com/cdn-cgi/trace`. Global selected Japan 04 is *not* the OpenAI fallback backend.

Actual previous **Shadowrocket Test Rules** checks: `chatgpt.com`, `ws.chatgpt.com`, `api.openai.com` matched `OpenAI-Resilience`. The active copy's rule source is blackmatrix7 OpenAI.list, according to the local offline database backup. The current protected Shadowrocket Group Container cannot be read reliably by a background agent; listing its directory hung and was terminated. Do not bypass TCC, change compiled rules, or claim live matches for untested domains.

Sources:
- OpenAI official: https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps
- Third-party rule set (last rule-header date 2025-06-06): https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/OpenAI/OpenAI.list
- Local safe overlay: `../examples/shadowrocket-openai-domain-overlay.fragment.conf`

## Static gaps, not proof of current routing failure

Domains or suffixes already covered by blackmatrix7's OpenAI.list include: `*.openai.com` (therefore `desktop.chat.openai.com`, `auth.openai.com` and `cdn.platform.openai.com`), `*.chatgpt.com` (therefore `ws.chatgpt.com`), `*.oaistatic.com`, `*.oaiusercontent.com`, `*.intercom.io`, `*.intercomcdn.com`, `*.stripe.com`, and `*.sentry.io`.

OpenAI-owned entries missing from this list: `*.oaistatsig.com`, `cdn.openaimerge.com` (covered by proposed `*.openaimerge.com`). These are the two safe, narrow static additions in the example overlay. They are **not currently applied**.

Shared domains that are not in this OpenAI rule set and must have their *actual policy* tested: `challenges.cloudflare.com`, `cdn.workos.com`, `setup.workos.com`, `forwarder.workos.com`, `frontend-apps-multi-region.workos.com`, `images.workoscdn.com`, `workos.imgix.net`, `*.ct.sendgrid.net`, and `rum.browser-intake-datadoghq.com`. `humb.apple.com` is Apple-operated; keep existing policies unless a verified requirement changes. **Do not route globally shared challenge, WorkOS, Apple, or SendGrid domains to the OpenAI exit without checking other app impacts.** Unmatched in one rule set does not mean DIRECT; the active config contains other rules.

## Anonymous transport observations (Mac mini, 2026-10-23 afternoon)

With HTTP proxy at 127.0.0.1:1082, a public `/cdn-cgi/trace` request returned HTTP 200 and observed egress US-SEA. `ws.chatgpt.com` responded 404 at URL `/` with a successful TLS handshake: this is *not* a WebSocket Upgrade validation. `auth.openai.com` returned anonymous 403, `challenges.cloudflare.com` anonymous 200. `desktop.chat.openai.com` TLS handshake ended with `curl: (35) SSL_ERROR_SYSCALL`; this **does not prove** the authenticated client route failed, but is worth comparing with Shadowrocket rule hit and a different node.

Actual desktop logs contained `Thread catalog sync failed` (authenticated 403), client Cloudflare challenge, and PubSub close/reopen events. Do not copy message text, tokens or full client logs into this repository.

## Required in-app rule test

Use Shadowrocket > 配置 > 测试规则 with the current active copy, without editing anything. Record only destination, matching rule, chosen policy/group and backend name if exposed:

1. `chatgpt.com` and `ws.chatgpt.com`: control checks, expect `OpenAI-Resilience`.
2. `desktop.chat.openai.com`, `auth.openai.com`: same suffix, expect `OpenAI-Resilience` unless an earlier override.
3. `oaistatsig.com`, `cdn.openaimerge.com`: check whether other rules already route correctly, before adding narrow overlay.
4. `challenges.cloudflare.com`, `cdn.workos.com`, `frontend-apps-multi-region.workos.com`: focus on authentication/challenge route; inspect other matched rules and avoid unreviewed shared-domain changes.
5. `tcr9i.chat.openai.com` and `cdn.platform.openai.com`: covered controls.

If only OpenAI-owned missing suffixes are routed incorrectly, add the two explicit rules from the example **through the app's official rule editor**, above broad rules. Test again after saving and verify the active copy; retain original `sr_cnip.conf` as rollback. Do not modify active routing from terminal or directly edit Shadowrocket internal SQLite.

## Failover verification boundary

- In native mode, the external `shadowrocket://select` API was observed to return success **without selecting** a new node. Guardian must never invoke it while the native fallback is active.
- Guardian v1.4.7 adds *passive sampled public-edge* incident evidence: start of failed probes, elapsed sampled outage, last good observed exit IP, recovered observed exit IP, and changed/not-changed. This **never proves** a native Shadowrocket policy backend switch; the status field deliberately says `native_backend_switch_verified=false`. An IP change may arise for other reasons; unchanged IP cannot disprove internal selection.
- True acceptance still needs either a naturally failing primary backend *with Shadowrocket-native policy/backend logs* and authenticated ChatGPT/WebSocket success, or a separately approved controlled outage (save config, timebox, restore, confirm no active work disrupted). Public HTTP 200 or a unit test alone cannot close this gate.
