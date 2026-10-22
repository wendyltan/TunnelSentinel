# TunnelSentinel handoff

- Snapshot: 2026-10-22, Mac mini, local development worktree on `feature/tunnelsentinel-health-dashboard-20261022` (refresh `git log -1` and `git status -sb`).
- Version: 1.3.0. Existing project behavior: 30-second link checks, 150-second failure window, 3 failures to switch and 300-second cooldown. Kept intact.
- Changes: categorized recent Cloudflare / HTTP 429 / connection / repeated layout events from Codex app logs; diagnostic status separate from `healthy`; custom AppKit menu and events window; 5-second status view refresh; *attempted* ~2-second node read; SIGUSR1 manual probe; guarded installer signing.
- Live: guard and menu LaunchAgents running on Mac mini. User's real configuration preserved. Pre-update scripts/menu/config backed up under `~/Library/Application Support/OpenAILinkGuardian/backups/20261022-pre-1.3/`. No ChatGPT, Codex, Shadowrocket, Tailscale restart, no user data deletion.
- Known limitation: on this machine, Shadowrocket App Group preference reads from LaunchAgents stall/restrict access. Guardian sets `current_node_verified=false`. Menu marks last-known node **未核实**, times out node lookup, and suspends retries after an OS-level timeout. Do not claim real 2-second node sync was accepted.
- Checks: 27 Python tests passed under Python 3.10, Swift compiled, live guards and menu launched, public edge health running; real force-probe signal updated status. macOS menu open/layout user acceptance is **NOT RUN**.
- Next: ask the user to open TunnelSentinel in the menu bar and review actual layout, node accuracy and menu actions. If node reads are blocked, research low-permission ways to get selected server before considering any broader system permission request.

## Branding follow-up — 2026-10-22

- User reported black/low-contrast menu-bar label and unattractive documentation; requested menu bar mark, app icon, README.
- Fixed menu button from coloured Unicode marker to native macOS template image, auto-coloured with current appearance; kept title `AI` at native text contrast.
- Added self-contained icon geometry in `branding/GenerateBranding.swift` with `branding/build-assets.sh`, building native `AppIcon.icns`, `MenuBarTemplate.png` and a light README preview.
- Installer now packages a signed `~/Applications/TunnelSentinel.app` (`LSUIElement=true`), launches it via existing LaunchAgent label, and saves previous binary/agent to an exact dated backup directory. Guardian/Shadowrocket/ChatGPT unchanged.
- Replaced README with compact product-style overview, honest status semantics, embedded logo, installation, local-first privacy, defaults, FAQs. No fake screenshot or fake repository link.
- Verification: icon files generated, Swift build, signed bundle verified, LaunchAgent and guardian both running. Menu real-world contrast and Finder presentation are pending visual acceptance.
- Next: user visually checks menu status visibility in light/dark menu bar and Finder app icon. Preserve current branch and check Git status/commit before further updates.


## Reliability milestone — 2026-10-22

- User requested stronger recovery instead of cosmetic UI, and asked why a new branch was created. No new branch for this stage: retain `feature/tunnelsentinel-health-dashboard-20261022`; it was originally created to protect main per the root AGENTS development guidance, not mandatory for every change.
- Actual fault: 2026-10-22 20:57 onward, Shadowrocket selected `🇳🇱 Netherlands 01`; GitHub worked but ChatGPT edge and API timed out. Old `config.json` names `日本2｜解锁流媒体` etc no longer matched the current subscription. A carefully bounded URL selection attempt for `🇯🇵 Japan 14` returned success but Shadowrocket's selected server DID NOT change. This indicates selection control path is ineffective, independently of stale names.
- v1.4 changes: 30s normal / 10s degraded check interval, candidate list from last 72h actually successful guardian log records, two-check learning, skip old unproven names, single candidate per attempted recovery, abort unconfirmed switch with 15m backoff, manual node-change grace, clear false failover score upon healthy probe, no rotation solely from desktop log errors, explicit `recovery_state` / `recovery_reason` / retry seconds in status & menu. A verified fresh public edge probe is required after confirmed selection.
- Keep user's actual live config backed up. Never promise guaranteed automatic recovery while macOS Shadowrocket URL-scheme selection is unproven. The next meaningful integration step is a controlled investigation of Shadowrocket-native `fallback`/`url-test` groups or a properly permissioned selection method and actual user acceptance. Do not directly edit encrypted Shadowrocket files or subscription secrets.
- No status of full end-to-end auto-switch as PASS until a real observable node change and new successful public probe are both recorded.

- 2026-10-22 live verification: app activation followed by documented `shadowrocket://select?s=...` also did **not** change the selected server; `🇳🇱 Netherlands 01` remained selected, ChatGPT edge timed out. User-visible recovery cannot be claimed complete.
- Live v1.4 deployment: guard v1.4.0 and signed menu 1.4.0; newly configured recent names `Japan 14, Seattle 05, San Jose 07, Seattle 01` (actual UTF8 names in live config), original config/backing script/status at `~/Library/Application Support/OpenAILinkGuardian/backups/20261022-pre-recovery-v14/`. Only TunnelSentinel services restarted. On 21:35:03, `recovery_state=selector_unavailable` with explicit message and ~882 seconds of backoff; no more old-name sequence.

- Final bounded test: even foreground `open -a /Applications/Shadowrocket.app shadowrocket://select?s=...` returned exit 0 but selected server did not change. Do not treat any variant of open() success as evidence of a working Mac 2.2.92 selector.
- 1.4 candidate cache refreshed every 5 minutes from successful guardian log records; expires >72-hour nodes even on long-running daemon. Added test for expiry.
