# TunnelSentinel development rules

1. Begin with `/Volumes/ExtSSD/AGENTS.md`, then `README.md` and `HANDOFF.md` (if present). Check Git branch, local config, current LaunchAgent state before modifying.
2. Never log ChatGPT messages, cookies, authentication tokens, Shadowrocket subscriptions, or other credentials.
3. `healthy` is **public proxy reachability**, not chat/service availability. Keep recent client warnings separate from proxy failure scores. Cloudflare challenges and HTTP 429 must **not** by themselves trigger node rotation.
4. Preserve live `~/Library/Application Support/OpenAILinkGuardian/config.json`. Do not restart ChatGPT, Codex or Shadowrocket when updating this tool. Back up live binaries before installation.
5. macOS can stall a LaunchAgent trying to open Shadowrocket's protected Group Container. Every such read must be bounded; never synchronously open that container on the guardian/UI main thread. If unreadable, report node unverified instead of showing stale data as live.
6. Regression: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m unittest discover -s tests -q`; UI build: `swiftc -parse-as-library -O -framework AppKit menubar/TunnelSentinelMenu.swift -o /tmp/TunnelSentinelMenu-preview` (preview only). Installation uses `install-menubar.sh` to create/sign `~/Applications/TunnelSentinel.app`, with a stable identifier and `LSUIElement`; keep the previous LaunchAgent and binary backed up.
7. A passing compiler/test suite does not equal a successful macOS menu usability check. Require real launch status and user visual acceptance.

8. Menu bar branding must be an `NSImage.isTemplate=true` glyph with native system tint (never set text `contentTintColor` to a fixed color). Branded Finder icon comes from the signed app bundle. Use `branding/build-assets.sh` to regenerate bundled assets and keep README image references valid.
