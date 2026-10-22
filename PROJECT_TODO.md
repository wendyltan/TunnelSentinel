# TunnelSentinel — outstanding acceptance

## P0 · Proven autonomous recovery (OPEN)

- [x] Stop looping over stale subscription names; use recently successful verified candidates.
- [x] Shorten degraded detection checks without changing normal network checks.
- [x] Do not auto-rotate from mere 429/Cloudflare client diagnostics.
- [x] Verify selection and a fresh edge request before declaring recovery; classify selector failure and back off.
- [x] Menu displays recovery failure and offers open-Shadowrocket action.
- [ ] **Prove automatic node selection on this Mac.** Both background URL scheme and foreground activated URL scheme returned without changing the selected node. Do not claim failover succeeds. Investigate Shadowrocket native fallback/url-test groups or a verified, explicitly approved macOS control path. Do not edit subscription secrets or install competing proxy stacks.
- [ ] Prove full integration: selected node physically changes and ChatGPT public probe succeeds, then app diagnostics recover after fresh client events.
- [ ] Human visual acceptance of menu recovery state and action.

## P1 · Operational verification

- [ ] Verify healthy-to-degraded-to-recovered timing with a user-approved controlled outage. Never interrupt active tasks merely for tests.
- [ ] Verify Shadowrocket policy/routing is correct for the OpenAI destinations; generic GitHub 200 does not prove the same proxy route.
- [ ] Observe repeated events across one day; no unnecessary restarts, no duplicate node selection storms, no accidental stale data reported as fresh.

Use `AGENTS.md` and `HANDOFF.md` for safety and current deployment facts; keep README public-facing rather than as a temporary checklist.
