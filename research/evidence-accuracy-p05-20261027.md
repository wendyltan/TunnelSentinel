# TunnelSentinel P0.5 · ChatGPT monitoring evidence accuracy

Date: 2026-10-27, China Standard Time. Scope: monitoring interpretation, timeout coherence, presentation only. No changes to subscriptions, Shadowrocket routing, node selection, auto-failover switches or the existing tunnel-reconnect preference.

## Why
The previous production capture showed a primary public-edge GET 200 after about 6.8 seconds while the independent six-target anonymous deep probe had a 6-second timeout and could mark ChatGPT degraded. The logs were real, but the interpretation wrongly implied service failure. The historical "known-good" server set was derived from two public trace HTTP 200 responses under a global selector, not from authenticated GPT or per-request physical node routing. Absence of a recently recognized client error never established an authenticated ChatGPT/Computer Use success.

## Changes
- Deep public curl checks now use connect timeout 5 seconds and overall request maximum 10 seconds, matching primary Guardian; subprocess timeout 12 seconds. Individual target capture has observed_at, and UI displays deep, Codex client and AI matrix collection times.
- Raw network probe results remain untouched. With the local listener present, one public-edge timeout becomes amber "verification pending"; a second consecutive failure confirms offline. A missing local proxy listener is immediately failed. The incident timeline sees these debounced workflow-axis states, while original failures and durations are kept for diagnosis.
- Healthy primary public GET overrides a simultaneous anonymous deep timeout as a ChatGPT transport verdict; ChatGPT is "partial / public access only" and never claims authenticated dialogue, upload, image generation or Computer Use success. Deep HTTP 403/404 and WebSocket synthetic GET / are not recognized as successful authenticated upgrades.
- overall_status now distinguishes reachable, verifying, attention and offline; business_status distinguishes unverified, client_metadata_only and attention. No positive authenticated task success is inferred from Codex GET /models or POST /responses HTTP 200; they remain actual client HTTP metadata, not completed generated output.
- Keep legacy known_good_candidates for compatibility but add historical_public_edge_nodes and known_good_candidates_scope, explicitly describing historical global-selected public GET200 evidence, not GPT node health or current subscription inventory. The Guardian learning log is now precise.
- Menu UI status and sidebar follow the same amber pending-network state. Overview 2x2 cards show their axis observed time; diagnostic probe rows include sample time, and AI matrix shows last collection time.

## Privacy and operations
No account credentials, cookies, conversation payloads or probe raw bodies are stored in new fields. Existing user-defined settings remain unchanged. No artificial disconnect was injected. New tests cover a one-off timeout, repeated outage, proxy listener loss, the conflicting deep probe, stale evidence, business-not-validated, node evidence scope, timestamps and source authenticity.

## Production evidence
Guardian installed with backup in ~/Library/Application Support/OpenAILinkGuardian/backups/accuracy-p05-20261027-175304. The signed menu App installed at ~/Applications/TunnelSentinel.app with a timestamped backup. On actual live data after Guardian restart, network=ok, chatgpt=partial, codex=partial, computer_use=unknown; business_status=client_metadata_only and raw public edge GET 200. The actual macOS overview and diagnosis screenshots were inspected. The Shadowrocket port 1082 and user safety switches were preserved.

## Limits
This corrects transport evidence integrity, not the root cause of occasional node packet loss. Historical Cloudflare public checks cannot prove stable authenticated GPT behavior or produce business-verified node recommendations. Those require trusted request-level route attribution and actual successful task evidence.
