# TunnelSentinel handoff

- Snapshot: 2026-10-22, Mac mini, local development worktree on `feature/tunnelsentinel-health-dashboard-20261022` (refresh `git log -1` and `git status -sb`).
- Version: 1.3.0. Existing project behavior: 30-second link checks, 150-second failure window, 3 failures to switch and 300-second cooldown. Kept intact.
- Changes: categorized recent Cloudflare / HTTP 429 / connection / repeated layout events from Codex app logs; diagnostic status separate from `healthy`; custom AppKit menu and events window; 5-second status view refresh; *attempted* ~2-second node read; SIGUSR1 manual probe; guarded installer signing.
- Live: guard and menu LaunchAgents running on Mac mini. User's real configuration preserved. Pre-update scripts/menu/config backed up under `~/Library/Application Support/OpenAILinkGuardian/backups/20261022-pre-1.3/`. No ChatGPT, Codex, Shadowrocket, Tailscale restart, no user data deletion.
- Known limitation: on this machine, Shadowrocket App Group preference reads from LaunchAgents stall/restrict access. Guardian sets `current_node_verified=false`. Menu marks last-known node **未核实**, times out node lookup, and suspends retries after an OS-level timeout. Do not claim real 2-second node sync was accepted.
- Checks: 27 Python tests passed under Python 3.10, Swift compiled, live guards and menu launched, public edge health running; real force-probe signal updated status. macOS menu open/layout user acceptance is **NOT RUN**.
- Next: ask the user to open TunnelSentinel in the menu bar and review actual layout, node accuracy and menu actions. If node reads are blocked, research low-permission ways to get selected server before considering any broader system permission request.
