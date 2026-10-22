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
